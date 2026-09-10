package net.bhl.matsim.uam.scoring;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.events.ActivityEndEvent;
import org.matsim.api.core.v01.events.ActivityStartEvent;
import org.matsim.api.core.v01.events.handler.ActivityEndEventHandler;
import org.matsim.api.core.v01.events.handler.ActivityStartEventHandler;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.api.experimental.events.EventsManager;

import com.google.inject.Inject;
import com.google.inject.Singleton;

/**
 * Measures actual durations of vertiport processing and waiting activities.
 */
@Singleton
public final class UAMVertiportActivityWaitTracker implements
		ActivityStartEventHandler,
		ActivityEndEventHandler {

	private static final Set<String> WAITING_ACTIVITY_TYPES = Set.of(
			"vertiport_entry",
			"vertiport_boarding",
			"vertiport_arrival",
			"vertiport_interaction",
			"uam_interaction",
			"uam_terminal_wait");

	private final EventsManager eventsManager;
	private final Map<Id<Person>, ActivityStart> starts = new LinkedHashMap<>();

	@Inject
	public UAMVertiportActivityWaitTracker(EventsManager eventsManager) {
		this.eventsManager = eventsManager;
	}

	@Override
	public void handleEvent(ActivityStartEvent event) {
		if (WAITING_ACTIVITY_TYPES.contains(event.getActType())) {
			starts.put(event.getPersonId(), new ActivityStart(
					event.getActType(), event.getTime()));
		}
	}

	@Override
	public void handleEvent(ActivityEndEvent event) {
		ActivityStart start = starts.remove(event.getPersonId());
		if (start == null || !start.activityType().equals(event.getActType())) {
			return;
		}

		double duration = Math.max(0.0, event.getTime() - start.time());
		eventsManager.processEvent(new UAMVertiportActivityWaitEvent(
				event.getTime(),
				event.getPersonId(),
				event.getActType(),
				duration));
	}

	@Override
	public void reset(int iteration) {
		starts.clear();
	}

	private record ActivityStart(String activityType, double time) {
	}
}
