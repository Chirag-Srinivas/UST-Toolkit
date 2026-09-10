package net.bhl.matsim.uam.scoring;

import java.util.Map;

import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.events.Event;
import org.matsim.api.core.v01.events.HasPersonId;
import org.matsim.api.core.v01.population.Person;

/**
 * Reports realized time in a processing or waiting activity at a vertiport.
 */
public final class UAMVertiportActivityWaitEvent extends Event implements HasPersonId {
	public static final String EVENT_TYPE = "uam vertiport activity wait";
	public static final String ATTRIBUTE_ACTIVITY_TYPE = "activityType";
	public static final String ATTRIBUTE_DURATION = "duration";

	private final Id<Person> personId;
	private final String activityType;
	private final double duration;

	public UAMVertiportActivityWaitEvent(
			double time,
			Id<Person> personId,
			String activityType,
			double duration) {
		super(time);
		this.personId = personId;
		this.activityType = activityType;
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

	public String getActivityType() {
		return activityType;
	}

	public double getDuration() {
		return duration;
	}

	@Override
	public Map<String, String> getAttributes() {
		Map<String, String> attributes = super.getAttributes();
		attributes.put("person", personId.toString());
		attributes.put(ATTRIBUTE_ACTIVITY_TYPE, activityType);
		attributes.put(ATTRIBUTE_DURATION, Double.toString(duration));
		return attributes;
	}
}
