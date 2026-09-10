package net.bhl.matsim.uam.scoring;

import java.util.LinkedHashMap;
import java.util.Map;

import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.events.LinkEnterEvent;
import org.matsim.api.core.v01.events.PersonEntersVehicleEvent;
import org.matsim.api.core.v01.events.PersonLeavesVehicleEvent;
import org.matsim.api.core.v01.events.handler.LinkEnterEventHandler;
import org.matsim.api.core.v01.events.handler.PersonEntersVehicleEventHandler;
import org.matsim.api.core.v01.events.handler.PersonLeavesVehicleEventHandler;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.api.experimental.events.EventsManager;
import org.matsim.vehicles.Vehicle;

import com.google.inject.Inject;
import com.google.inject.Singleton;

import net.bhl.matsim.uam.run.UAMConstants;

/**
 * Measures passenger time from boarding until the aircraft starts takeoff.
 */
@Singleton
public final class UAMPostBoardingQueueTracker implements
		PersonEntersVehicleEventHandler,
		PersonLeavesVehicleEventHandler,
		LinkEnterEventHandler {

	private static final String TAKEOFF_LINK_PREFIX = "link_fato_takeoff_";

	private final EventsManager eventsManager;
	private final Map<Id<Vehicle>, Map<Id<Person>, Double>> boardedPassengers =
			new LinkedHashMap<>();

	@Inject
	public UAMPostBoardingQueueTracker(EventsManager eventsManager) {
		this.eventsManager = eventsManager;
	}

	@Override
	public void handleEvent(PersonEntersVehicleEvent event) {
		if (!isUAMVehicle(event.getVehicleId())
				|| event.getPersonId().toString().equals(event.getVehicleId().toString())) {
			return;
		}

		boardedPassengers
				.computeIfAbsent(event.getVehicleId(), ignored -> new LinkedHashMap<>())
				.put(event.getPersonId(), event.getTime());
	}

	@Override
	public void handleEvent(PersonLeavesVehicleEvent event) {
		Map<Id<Person>, Double> passengers = boardedPassengers.get(event.getVehicleId());
		if (passengers == null) {
			return;
		}

		passengers.remove(event.getPersonId());
		if (passengers.isEmpty()) {
			boardedPassengers.remove(event.getVehicleId());
		}
	}

	@Override
	public void handleEvent(LinkEnterEvent event) {
		if (!event.getLinkId().toString().startsWith(TAKEOFF_LINK_PREFIX)) {
			return;
		}

		Map<Id<Person>, Double> passengers = boardedPassengers.remove(event.getVehicleId());
		if (passengers == null) {
			return;
		}

		for (Map.Entry<Id<Person>, Double> passenger : passengers.entrySet()) {
			double duration = Math.max(0.0, event.getTime() - passenger.getValue());
			eventsManager.processEvent(new UAMPostBoardingQueueEvent(
					event.getTime(),
					passenger.getKey(),
					event.getVehicleId(),
					duration));
		}
	}

	@Override
	public void reset(int iteration) {
		boardedPassengers.clear();
	}

	private static boolean isUAMVehicle(Id<Vehicle> vehicleId) {
		return vehicleId.toString().startsWith(UAMConstants.vehicle);
	}
}
