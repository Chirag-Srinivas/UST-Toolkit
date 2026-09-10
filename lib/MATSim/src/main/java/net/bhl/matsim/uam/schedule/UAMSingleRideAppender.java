package net.bhl.matsim.uam.schedule;

import java.util.Collections;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedList;
import java.util.List;
import java.util.concurrent.ExecutionException;

import org.matsim.contrib.dvrp.path.VrpPathWithTravelData;
import org.matsim.contrib.dvrp.path.VrpPaths;
import org.matsim.contrib.dvrp.schedule.DefaultDriveTask;
import org.matsim.contrib.dvrp.schedule.DefaultStayTask;
import org.matsim.contrib.dvrp.schedule.DriveTask;
import org.matsim.contrib.dvrp.schedule.Schedule;
import org.matsim.contrib.dvrp.schedule.Schedules;
import org.matsim.contrib.dvrp.schedule.StayTask;
import org.matsim.contrib.dvrp.schedule.Task;
import org.matsim.core.router.util.LeastCostPathCalculator;
import org.matsim.core.router.util.LeastCostPathCalculator.Path;
import org.matsim.core.router.util.TravelTime;

import com.google.inject.Inject;
import com.google.inject.name.Named;

import net.bhl.matsim.uam.infrastructure.UAMVehicle;
import net.bhl.matsim.uam.passenger.UAMRequest;
import net.bhl.matsim.uam.run.UAMConstants;

/**
 * This class adds tasks for each vehicle schedule based on the requests
 *
 * @author balacmi (Milos Balac), RRothfeld (Raoul Rothfeld)
 */
public class UAMSingleRideAppender {
	@Inject
	@Named(UAMConstants.uam)
	private LeastCostPathCalculator uamPathCalculator;

	@Inject
	@Named(UAMConstants.uam)
	private TravelTime travelTime;

	private List<AppendTask> tasks = new LinkedList<>();

	/**
	 * @param request UAM request
	 * @param vehicle UAM Vehicle
	 * @param now     simulation step now
	 *                <p>
	 *                This method generates the paths for pickup and drop-off and
	 *                create a new AppendTask containing this information. The new
	 *                AppendTask is added to the AppendTask list.
	 */
	public void schedule(UAMRequest request, UAMVehicle vehicle, double now) {
		schedule(Collections.singletonList(request), vehicle, now);
	}

	/**
	 * Schedules several compatible requests on one aircraft. All requests must
	 * share the same origin and destination, and their combined passenger count
	 * must not exceed the aircraft capacity.
	 */
	public void schedule(Collection<UAMRequest> requests, UAMVehicle vehicle, double now) {
		if (requests.isEmpty())
			throw new IllegalArgumentException("Cannot schedule an empty UAM request batch");
		tasks.add(new AppendTask(requests, vehicle, now));
	}

	// There is a difference between an AppendTask and a Task that implements the
	// Task interface.

	// Uses the AppendTasks from the list containing the paths to generate the Tasks
	// (Tasks that implements the Task interface) and add them in order to the
	// vehicle schedule
	public void schedule(AppendTask task) throws ExecutionException, InterruptedException {
		List<UAMRequest> requests = task.requests;
		UAMRequest request = requests.get(0);
		UAMVehicle vehicle = task.vehicle;
		double now = task.time;

		int passengerCount = requests.stream().mapToInt(UAMRequest::getPassengerCount).sum();
		if (passengerCount > vehicle.getCapacity())
			throw new IllegalArgumentException("UAM request batch exceeds aircraft capacity");
		for (UAMRequest pooledRequest : requests) {
			if (!pooledRequest.getFromLink().getId().equals(request.getFromLink().getId())
					|| !pooledRequest.getToLink().getId().equals(request.getToLink().getId()))
				throw new IllegalArgumentException("Pooled UAM requests must share origin and destination");
		}
		Schedule schedule = vehicle.getSchedule();

		StayTask stayTask = (StayTask) Schedules.getLastTask(schedule);
		boolean requiresPickupFlight = !stayTask.getLink().getId().equals(request.getFromLink().getId());

		double startTime = stayTask.getStatus() == Task.TaskStatus.STARTED ? now : stayTask.getBeginTime();
		double scheduleEndTime = schedule.getEndTime();

		Path pickupPath = uamPathCalculator.calcLeastCostPath(stayTask.getLink().getToNode(),
				request.getFromLink().getFromNode(), startTime, null, null);

		VrpPathWithTravelData pickupPathWithTravelData = VrpPaths.createPath(stayTask.getLink(), request.getFromLink(),
				startTime, pickupPath, travelTime);
		DriveTask pickupFlyTask = new DefaultDriveTask(UAMTaskType.FLY, pickupPathWithTravelData);

		double pickUpTaskStartTime = Math.max(now,
				requests.stream().mapToDouble(UAMRequest::getEarliestStartTime).max().orElse(now));
		// For the case when the Aircraft is not already at the correct station:
		if (requiresPickupFlight)
			pickUpTaskStartTime = Math.max(pickUpTaskStartTime, pickupPathWithTravelData.getArrivalTime());

		double flyTaskStartTime = pickUpTaskStartTime + vehicle.getBoardingTime();
		UAMPickupTask pickupTask = new UAMPickupTask(pickUpTaskStartTime, flyTaskStartTime, request.getFromLink(),
				vehicle.getBoardingTime(), requests);

		Path dropoffPath = uamPathCalculator.calcLeastCostPath(request.getFromLink().getToNode(),
				request.getToLink().getFromNode(), flyTaskStartTime, null, null);

		VrpPathWithTravelData dropoffPathWithTravelData = VrpPaths.createPath(request.getFromLink(),
				request.getToLink(), flyTaskStartTime, dropoffPath, travelTime);
		DriveTask dropoffFlyTask = new DefaultDriveTask(UAMTaskType.FLY, dropoffPathWithTravelData);

		double dropOffStartTime = flyTaskStartTime + dropoffPathWithTravelData.getTravelTime();
		double tatStartTime = dropOffStartTime + vehicle.getDeboardingTime();
		UAMDropoffTask dropoffTask = new UAMDropoffTask(dropOffStartTime, tatStartTime, request.getToLink(),
				vehicle.getDeboardingTime(), requests);

		double tatEndTime = tatStartTime + vehicle.getTurnAroundTime();
		StayTask turnAroundTask = new DefaultStayTask(UAMTaskType.TURNAROUND, tatStartTime, tatEndTime, request.getToLink());

		double stayEndTime = pickUpTaskStartTime;
		if (requiresPickupFlight)
			stayEndTime = startTime;
		stayTask.setEndTime(stayEndTime);

		if (requiresPickupFlight) {
			schedule.addTask(pickupFlyTask);

			StayTask uamStayTask = new DefaultStayTask(UAMTaskType.STAY, pickupFlyTask.getEndTime(), pickUpTaskStartTime,
					pickupFlyTask.getPath().getToLink());
			schedule.addTask(uamStayTask);
		}

		schedule.addTask(pickupTask);
		schedule.addTask(dropoffFlyTask);
		schedule.addTask(dropoffTask);
		schedule.addTask(turnAroundTask);
		schedule.addTask(
				new DefaultStayTask(UAMTaskType.STAY, turnAroundTask.getEndTime(), scheduleEndTime, turnAroundTask.getLink()));
	}

	public void update() {
		// TODO: This can be made more efficient if one knows which ones have
		// just been added and which ones are still
		// to be processed. Depends mainly on if "update" is called before new
		// tasks are submitted or after ...
		try {
			for (AppendTask task : tasks)
				schedule(task);
		} catch (ExecutionException | InterruptedException e) {
			throw new RuntimeException(e);
		}

		tasks.clear();
	}

	private class AppendTask {
		final public List<UAMRequest> requests;
		final public UAMVehicle vehicle;

		final public double time;

		public AppendTask(Collection<UAMRequest> requests, UAMVehicle vehicle, double time) {
			this.requests = new ArrayList<>(requests);
			this.vehicle = vehicle;
			this.time = time;
		}
	}
}
