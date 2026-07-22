import json, os, vertexai
from vertexai import agent_engines

PROJECT = "project-53bf8b85-eb44-4391-a2e"
LOCATION = "us-west1"
STAGING_BUCKET = f"gs://{PROJECT}-adk-staging"
ENGINE_ID = os.environ.get("ENGINE_ID", "2073459027659980800")

def main(request=None):
    vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=STAGING_BUCKET)
    ae = agent_engines.AgentEngine(
        f"projects/538412438779/locations/us-west1/reasoningEngines/{ENGINE_ID}"
    )
    sess = ae.create_session(user_id="scheduler")
    results = []
    for ev in ae.stream_query(user_id="scheduler", session_id=sess["id"],
                              message="周期检查：请检查当前TA分配状态，继续未完成进化。"):
        results.append(str(ev)[:300])
    return (json.dumps({"engine_id": ENGINE_ID, "session_id": sess["id"], "events": len(results)}),
            200, {"Content-Type": "application/json"})
