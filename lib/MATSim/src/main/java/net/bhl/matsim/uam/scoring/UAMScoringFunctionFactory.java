package net.bhl.matsim.uam.scoring;

import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.events.Event;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.scoring.ScoringFunction;
import org.matsim.core.scoring.ScoringFunctionFactory;
import org.matsim.core.scoring.SumScoringFunction;
import org.matsim.core.scoring.functions.CharyparNagelScoringFunctionFactory;
import org.matsim.core.scoring.functions.ModeUtilityParameters;
import org.matsim.core.scoring.functions.ScoringParameters;
import org.matsim.core.scoring.functions.ScoringParametersForPerson;
import org.matsim.core.scoring.functions.SubpopulationScoringParameters;

import com.google.inject.Inject;
import com.google.inject.Singleton;

import net.bhl.matsim.uam.run.UAMConstants;

/**
 * Creates the standard MATSim scorer with UAM-specific processing and waiting
 * components. UAM in-vehicle time remains in the standard mode scorer.
 */
@Singleton
public class UAMScoringFunctionFactory implements ScoringFunctionFactory {
	private final ScoringFunctionFactory standardFactory;
	private final ScoringParametersForPerson scoringParameters;

	@Inject
	public UAMScoringFunctionFactory(Scenario scenario) {
		standardFactory = new CharyparNagelScoringFunctionFactory(scenario);
		scoringParameters = new SubpopulationScoringParameters(scenario);
	}

	@Override
	public ScoringFunction createNewScoringFunction(Person person) {
		SumScoringFunction scoringFunction =
				(SumScoringFunction) standardFactory.createNewScoringFunction(person);
		ScoringParameters parameters = scoringParameters.getScoringParameters(person);

		ModeUtilityParameters uamModeParameters = parameters.modeParams.get(UAMConstants.uam);
		if (uamModeParameters == null) {
			throw new IllegalStateException("Missing scoring parameters for UAM mode.");
		}

		scoringFunction.addScoringFunction(new UAMWaitingScoring(
				parameters.marginalUtilityOfWaiting_s,
				uamModeParameters.marginalUtilityOfTraveling_s));

		return scoringFunction;
	}

	/**
	 * Scores realized vertiport processing directly with waiting utility, and
	 * converts the pre-boarding and post-boarding portions already included in
	 * the UAM leg from travel utility to waiting utility.
	 */
	private static final class UAMWaitingScoring
			implements SumScoringFunction.ArbitraryEventScoring {

		private final double marginalUtilityOfWaiting_s;
		private final double legWaitingAdjustment_s;
		private double score;

		private UAMWaitingScoring(
				double marginalUtilityOfWaiting_s,
				double marginalUtilityOfUAMTravel_s) {
			this.marginalUtilityOfWaiting_s = marginalUtilityOfWaiting_s;
			legWaitingAdjustment_s =
					marginalUtilityOfWaiting_s - marginalUtilityOfUAMTravel_s;
		}

		@Override
		public void handleEvent(Event event) {
			if (event instanceof UAMVertiportActivityWaitEvent waitEvent) {
				score += waitEvent.getDuration() * marginalUtilityOfWaiting_s;
			} else if (event instanceof UAMPreBoardingWaitEvent waitEvent) {
				score += waitEvent.getDuration() * legWaitingAdjustment_s;
			} else if (event instanceof UAMPostBoardingQueueEvent queueEvent) {
				score += queueEvent.getDuration() * legWaitingAdjustment_s;
			} else if (UAMVertiportActivityWaitEvent.EVENT_TYPE.equals(event.getEventType())) {
				score += duration(event, UAMVertiportActivityWaitEvent.ATTRIBUTE_DURATION)
						* marginalUtilityOfWaiting_s;
			} else if (UAMPreBoardingWaitEvent.EVENT_TYPE.equals(event.getEventType())) {
				score += duration(event, UAMPreBoardingWaitEvent.ATTRIBUTE_DURATION)
						* legWaitingAdjustment_s;
			} else if (UAMPostBoardingQueueEvent.EVENT_TYPE.equals(event.getEventType())) {
				score += duration(event, UAMPostBoardingQueueEvent.ATTRIBUTE_DURATION)
						* legWaitingAdjustment_s;
			}
		}

		private static double duration(Event event, String attributeName) {
			String value = event.getAttributes().get(attributeName);
			return value == null ? 0.0 : Math.max(0.0, Double.parseDouble(value));
		}

		@Override
		public void finish() {
		}

		@Override
		public double getScore() {
			return score;
		}
	}
}
