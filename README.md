# Nori – Streamlit UI for Bedrock KB (user_id‑filtered) via Lambda

This Streamlit app talks to your Lambda that performs:
1. **Retrieve** from a Bedrock Knowledge Base with a **strict metadata filter** on `user_id`  
2. **Generate** an answer via **Anthropic Claude 3 Haiku** on Bedrock

## Quickstart

1. **Python env**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set env vars** (or put them in `.streamlit/secrets.toml` or set in the sidebar):
   ```bash
   export AWS_REGION=ca-central-1
   export LAMBDA_NAME=YourLambdaFunctionName
   export USER_ID=userA
   # Optional HTTPS path via API Gateway instead of direct Lambda invoke:
   # export API_URL="https://xxxxxx.execute-api.ca-central-1.amazonaws.com/prod/chat"
   # export USE_SIGV4=true   # if your API uses IAM auth
   ```

3. **Run**
   ```bash
   streamlit run app.py
   ```

4. **Use**
   - Enter your `user_id` (e.g., `userB`) and ask questions.
   - Expand **Context / Sources** to see retrieved chunks and metadata (including `user_id`).

## Notes

- **Direct Lambda mode** (default) requires AWS credentials on the machine where you run Streamlit that can `lambda:InvokeFunction` on your function. Typical options:
  - Export `AWS_PROFILE`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, or use SSO (`aws sso login` + `AWS_PROFILE`).
- **API Gateway mode** lets you avoid exposing `lambda:InvokeFunction` client-side. You can protect your API with **IAM (SigV4)** or other methods.
- The UI sends the payload shape your Lambda expects: `{"message": "...", "user_id": "..."}`. It is also compatible with your `_extract_payload` logic when using API Gateway mapping to wrap under `data` if you prefer.
- Returned fields (`answer`, `retrievalResults`, `hitCount`) are rendered; unknown metadata keys are ignored gracefully.
