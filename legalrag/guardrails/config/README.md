# NeMo Guardrails Configuration

The application loads `config.yml` with `RailsConfig.from_content` after
resolving `NEMO_LLM_ENGINE` and `NEMO_LLM_MODEL` from the runtime environment.
Do not put provider credentials in this directory or in source control.

The grounding check remains in Python because it verifies stable passage IDs
against the local corpus; NeMo is used for conversational input and output
rails.
