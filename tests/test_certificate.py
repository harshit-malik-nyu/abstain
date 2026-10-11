from types import SimpleNamespace
import pytest
from abstain.rule import certify_trajectories,calibrate_on_trajectories

def test_small_perfect_sample_cannot_certify_a_search():
 cases=[{'states':{'employment_income':{'label':'determinable'}}} for _ in range(100)]
 def run(case,scorer,threshold):return SimpleNamespace(committed=True,asked=[])
 assert calibrate_on_trajectories(cases,None,run).feasible
 assert not certify_trajectories(cases,None,run).feasible
 assert certify_trajectories(cases*10,None,run).feasible
 with pytest.raises(ValueError):certify_trajectories(cases,None,run,grid=1)
