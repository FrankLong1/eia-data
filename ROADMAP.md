# Project Roadmap

## Core Strategic Questions: Data Centers, Energy, and Load Growth

### The Big Picture: Why This Matters
The U.S. power grid faces unprecedented load growth from AI data centers, EVs, and electrification. Understanding where and when generation capacity exists is critical for:
- **Data center operators**: Where to site facilities to access clean, reliable, affordable power
- **Grid operators**: How to integrate large flexible loads without infrastructure upgrades
- **Policymakers**: Where targeted investments can unlock stranded renewable capacity
- **Investors**: Which regions offer the best risk/return for energy-intensive facilities

### Fundamental Questions We're Answering

#### 1. Where is the untapped capacity?
- **Curtailment mapping**: Which regions have the most renewable energy being wasted?
- **Underutilized assets**: Which gas plants are running far below capacity?
- **Transmission bottlenecks**: Where does generation exceed local transmission limits?
- **Ownership concentration**: Which companies own the most underutilized generation?

#### 3. What's the economic value?
- **Curtailment costs**: How many millions in lost revenue from wasted generation?
- **Flexibility premium**: What's the $ value of load that can turn off in milliseconds?
- **System savings**: How much infrastructure investment can be avoided?

#### 4. Where should data centers go?
- **Optimal locations**: Best sites for 24/7 carbon-free energy access?
- **Risk assessment**: Which locations have stable long-term renewable growth?

#### 5. How fast is this changing?
- **Load growth**: Which regions are seeing the fastest demand growth?

### Brainstorm: Additional Strategic Questions

#### Grid Resilience & Reliability
- **Extreme weather**: Which plants consistently fail during heat waves or cold snaps?
- **Forced outage patterns**: Can we predict plant reliability from historical generation data?

#### Technology Transitions
- **Coal retirement opportunities**: Which coal plants could be replaced with storage + renewables?
- **Gas plant economics**: At what utilization rate do gas plants become uneconomic?
- **Renewable integration limits**: Where is the grid hitting technical limits for renewable penetration?
- **Hydrogen potential**: Which locations have excess renewables suitable for green hydrogen?

### Specific Analysis Questions

#### Immediate Questions (Phases 1-2)
1. **Where is the most renewable curtailment happening?** (Phase 1.2)
2. **Which gas plants have the most spare capacity?** (Phase 2.2)
3. **What companies own the most underutilized generation?** (Phase 2.2)
4. **How much battery storage exists and where?** (Phase 2.3)

#### Strategic Questions (Phase 3+)
5. **Where should flexible loads (data centers) be located?** (Phase 3.1)
6. **What's the economic value of curtailment reduction?** (Phase 3.1)
7. **Can we identify inefficient/problematic plants from data?** (Phase 3.3)
8. **How do plant-level and BA-level analyses compare?** (Phase 3.2)


## Phase 1: Foundation & Data Quality (Immediate)

### 1.1 Plant Data Cleaning Module
**Priority**: High | **Status**: Not Started | **Dependencies**: None
- [ ] Create `PlantDataCleaner` class similar to `BAAggregateCleaner`
- [ ] Implement outlier detection using IQR method for generation values
- [ ] Validate generation against reported capacity limits
- [ ] Handle missing values with interpolation
- [ ] Add data quality reporting

### 1.2 Plant Curtailment Analysis
**Priority**: High | **Status**: Not Started | **Dependencies**: 1.1
- [ ] Implement `PlantCurtailmentAnalyzer` class
- [ ] Calculate plant-level curtailment potential
- [ ] Identify patterns by fuel type, especially renewable curtailment
- [ ] Compare results with BA-level analysis for validation

## Phase 2: Key Analysis Questions

### 2.1 Geographic Mapping & Visualization
**Priority**: Medium | **Status**: Not Started | **Dependencies**: 1.1, 1.2
- [ ] Create interactive map of plants with highest curtailment potential
- [ ] Identify geographic clusters of underutilized capacity
- [ ] Map proximity to major load centers and transmission infrastructure
- [ ] Visualize seasonal patterns by region

### 2.2 Gas Plant Analysis
**Priority**: High | **Status**: Not Started | **Dependencies**: 1.1
- [ ] Identify underutilized gas plants with spare capacity
- [ ] Calculate capacity factors and utilization rates
- [ ] Find companies/owners with most spare megawatts
- [ ] Map gas plant locations vs. renewable curtailment areas
- [ ] Analyze potential for gas-to-battery conversion opportunities
- [ ] Rank energy companies by total available generation capacity
- [ ] Create ownership concentration analysis of underutilized power generation
- [ ] Identify top 10 power generation owners with most idle capacity

### 2.3 Storage Infrastructure Analysis
**Priority**: Medium | **Status**: Not Started | **Dependencies**: 1.1
- [ ] Quantify scale of existing battery storage by region
- [ ] Map storage locations relative to curtailment hotspots
- [ ] Analyze storage utilization patterns
- [ ] Identify gaps where storage could reduce curtailment

# EVERYTHING BELOW IS MORE SPECULATIVE

## Phase 3: Strategic Insights 

### 3.1 Data Center Siting Analysis
**Priority**: High | **Status**: Not Started | **Dependencies**: 2.1, 2.2
- [ ] Identify optimal locations for flexible data center loads
- [ ] Calculate economic value of curtailment reduction
- [ ] Model different flexibility scenarios (50%, 80%, 100% flexible)
- [ ] Create decision matrix for site selection

### 3.2 Cross-Validation & Reporting
**Priority**: Medium | **Status**: Not Started | **Dependencies**: 1.2
- [ ] Compare plant-level vs BA-level curtailment estimates
- [ ] Generate state-by-state summary reports
- [ ] Create executive dashboard with key metrics
- [ ] Document methodology and assumptions

### 3.3 Methane Leakage Investigation
**Priority**: Low | **Status**: Research Needed | **Dependencies**: 2.2
- [ ] Research feasibility of detecting inefficient/leaking plants from generation data
- [ ] Analyze anomalous heat rates or efficiency patterns
- [ ] Cross-reference with EPA emissions data if available
- [ ] Flag plants for further investigation






# TODO LATER
* I am going to offload this data to a network attached storage, so want to make sure this all works with that, probably have it be able to point to any path and have it agnositcally work, that dir will be home to the ba_agg_data and plant_data

## Technical Debt & Improvements

- [ ] Add comprehensive logging throughout pipeline
- [ ] Implement proper error handling and recovery
- [ ] Add unit tests for all analysis modules
- [ ] Optimize API batch sizes based on performance testing
- [ ] Create data versioning system for reproducibility


