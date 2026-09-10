package net.bhl.matsim.uam.scoring;

import java.util.Map;

import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.events.Event;
import org.matsim.api.core.v01.events.HasPersonId;
import org.matsim.api.core.v01.population.Person;
import org.matsim.vehicles.Vehicle;

/**
 * Marks the end of a passenger's post-boarding, pre-airborne queue.
 */
public final class UAMPostBoardingQueueEvent extends Event implements HasPersonId {
	public static final String EVENT_TYPE = "uam post-boarding queue";
	public static final String ATTRIBUTE_DURATION = "duration";

	private final Id<Person> personId;
	private final Id<Vehicle> vehicleId;
	private final double duration;

	public UAMPostBoardingQueueEvent(
			double time,
			Id<Person> personId,
			Id<Vehicle> vehicleId,
			double duration) {
		super(time);
		this.personId = personId;
		this.vehicleId = vehicleId;
		this.duration = duration;
	}

	@Override
	public String getEventType() {
		return EVENT_TYPE;
	}

	@Override
	public Id<Person> getPersonId() {
		return personId;
	}

	public double getDuration() {
		return duration;
	}

	@Override
	public Map<String, String> getAttributes() {
		Map<String, String> attributes = super.getAttributes();
		attributes.put("person", personId.toString());
		attributes.put("vehicle", vehicleId.toString());
		attributes.put(ATTRIBUTE_DURATION, Double.toString(duration));
		return attributes;
	}
}
