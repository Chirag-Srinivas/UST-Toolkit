package net.bhl.matsim.uam.scoring;

import java.util.LinkedHashMap;
import java.util.Map;

import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.events.PersonArrivalEvent;
import org.matsim.api.core.v01.events.PersonDepartureEvent;
import org.matsim.api.core.v01.events.PersonEntersVehicleEvent;
import org.matsim.api.core.v01.events.handler.PersonArrivalEventHandler;
import org.matsim.api.core.v01.events.handler.PersonDepartureEventHandler;
import org.matsim.api.core.v01.events.handler.PersonEntersVehicleEventHandler;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.api.experimental.events.EventsManager;
import org.matsim.vehicles.Vehicle;

import com.google.inject.Inject;
import com.google.inject.Singleton;

import net.bhl.matsim.uam.run.UAMConstants;

/**
 * Measures each passenger's realized wait from UAM-leg departure to boarding.
 */
@Singleton
public final class UAMPreBoardingWaitTracker implements
		PersonDepartureEventHandler,
		PersonEntersVehicleEventHandler,
		PersonArrivalEventHandler {

	private final EventsManager eventsManager;
	private final Map<Id<Person>, Double> departures = new LinkedHashMap<>();

	@Inject
	public UAMPreBoardingWaitTracker(EventsManager eventsManager) {
		this.eventsManager = eventsManager;
	}

	@Override
	public void handleEvent(PersonDepartureEvent event) {
		if (UAMConstants.uam.equals(event.getLegMode())) {
			departures.put(event.getPersonId(), event.getTime());
		}
	}

	@Override
	public void handleEvent(PersonEntersVehicleEvent event) {
		if (!isUAMVehicle(event.getVehicleId())) {
			return;
		}

		Double departureTime = departures.remove(event.getPersonId());
		if (departureTime == null) {
			return;
		}

		double duration = Math.max(0.0, event.getTime() - departureTime);
		eventsManager.processEvent(new UAMPreBoardingWaitEvent(
				event.getTime(),
				event.getPersonId(),
				event.getVehicleId(),
				duration));
	}

	@Override
	public void handleEvent(PersonArrivalEvent event) {
		if (UAMConstants.uam.equals(event.getLegMode())) {
			departures.remove(event.getPersonId());
		}
	}

	@Override
	public void reset(int iteration) {
		departures.clear();
	}

	private static boolean isUAMVehicle(Id<Vehicle> vehicleId) {
		return vehicleId.toString().startsWith(UAMConstants.vehicle);
	}
}
