# Start the chaos controller + dashboard with a Groq-hosted model as the AI (fast, free tier).
# The key is read from the GROQ_API_KEY user environment variable, never from this file:
#   [Environment]::SetEnvironmentVariable('GROQ_API_KEY', '<your key>', 'User')
$key = [Environment]::GetEnvironmentVariable('GROQ_API_KEY', 'User')
if (-not $key) { $key = $env:GROQ_API_KEY }
if (-not $key) { Write-Error "GROQ_API_KEY is not set for this Windows user"; exit 1 }
$env:CHAOS_LLM_PROVIDER = 'openai'
$env:CHAOS_OPENAI_URL = 'https://api.groq.com/openai/v1'
# gpt-oss-120b answered the planner prompt in about 5 s and produced valid plans and diagnoses when tested
if (-not $env:CHAOS_OPENAI_MODEL) { $env:CHAOS_OPENAI_MODEL = 'openai/gpt-oss-120b' }
$env:OPENAI_API_KEY = $key
# each model has its own 8,000 tokens-per-minute budget on the free tier; these are
# tried in order when the main model answers 429 (rate limited)
if (-not $env:CHAOS_OPENAI_FALLBACK_MODELS) { $env:CHAOS_OPENAI_FALLBACK_MODELS = 'openai/gpt-oss-20b,qwen/qwen3.8-27b' }
# rules take over if the model has not answered in time
if (-not $env:CHAOS_LLM_TIMEOUT_S) { $env:CHAOS_LLM_TIMEOUT_S = '20' }
# shorter fixed waits for a live demo; set CHAOS_SPEED=normal for results you intend to report
if (-not $env:CHAOS_SPEED) { $env:CHAOS_SPEED = 'fast' }
& "$PSScriptRoot\.venv\Scripts\python.exe" -m chaos serve @args
