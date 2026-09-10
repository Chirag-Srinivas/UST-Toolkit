package net.bhl.matsim.uam.replanning;

import org.matsim.api.core.v01.population.HasPlansAndId;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.Plan;
import org.matsim.core.replanning.PlanStrategy;
import org.matsim.core.replanning.ReplanningContext;

/** Records the exact strategy assigned to a person, then delegates to MATSim. */
final class LoggedPlanStrategy implements PlanStrategy {
    static final String ATTRIBUTE_NAME = "replanningStrategy";

    private final String strategyName;
    private final PlanStrategy delegate;

    LoggedPlanStrategy(String strategyName, PlanStrategy delegate) {
        this.strategyName = strategyName;
        this.delegate = delegate;
    }

    @Override
    public void run(HasPlansAndId<Plan, Person> person) {
        if (!(person instanceof Person matsimPerson)) {
            throw new IllegalArgumentException("Expected a MATSim Person");
        }
        matsimPerson.getAttributes().putAttribute(ATTRIBUTE_NAME, strategyName);
        delegate.run(person);
    }

    @Override
    public void init(ReplanningContext replanningContext) {
        delegate.init(replanningContext);
    }

    @Override
    public void finish() {
        delegate.finish();
    }
}
