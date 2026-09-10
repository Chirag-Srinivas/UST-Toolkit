package net.bhl.matsim.uam.replanning;

import jakarta.inject.Provider;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.Plan;
import org.matsim.core.replanning.PlanStrategy;
import org.matsim.core.replanning.PlanStrategyImpl;
import org.matsim.core.replanning.selectors.RandomPlanSelector;

/** SelectRandom selector with person-level assignment logging. */
public final class LoggedSelectRandom implements Provider<PlanStrategy> {
    @Override
    public PlanStrategy get() {
        PlanStrategy delegate = new PlanStrategyImpl.Builder(
                new RandomPlanSelector<Plan, Person>())
                .build();
        return new LoggedPlanStrategy("SelectRandom", delegate);
    }
}
