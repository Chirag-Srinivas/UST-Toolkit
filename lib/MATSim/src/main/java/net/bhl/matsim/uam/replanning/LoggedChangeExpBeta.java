package net.bhl.matsim.uam.replanning;

import jakarta.inject.Inject;
import jakarta.inject.Provider;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.Plan;
import org.matsim.core.config.groups.ScoringConfigGroup;
import org.matsim.core.replanning.PlanStrategy;
import org.matsim.core.replanning.PlanStrategyImpl;
import org.matsim.core.replanning.selectors.ExpBetaPlanChanger;

/** ChangeExpBeta selector with person-level assignment logging. */
public final class LoggedChangeExpBeta implements Provider<PlanStrategy> {
    @Inject
    private ScoringConfigGroup scoringConfig;

    @Override
    public PlanStrategy get() {
        PlanStrategy delegate = new PlanStrategyImpl.Builder(
                new ExpBetaPlanChanger<Plan, Person>(scoringConfig.getBrainExpBeta()))
                .build();
        return new LoggedPlanStrategy("ChangeExpBeta", delegate);
    }
}
