const GATEWAY_BASE =
  process.env.NEXT_PUBLIC_GATEWAY_URL ??
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080/api"}/gateway`;

async function gatewayRequest<T>(
  path: string,
  apiKey: string | null,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  const res = await fetch(`${GATEWAY_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...options.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Gateway error ${res.status}`);
  }
  return res.json();
}

export async function register(
  walletAddress: string,
  signature: string,
  message: string,
) {
  return gatewayRequest<{ api_key: string; wallet_address: string }>(
    "/register",
    null,
    {
      method: "POST",
      body: JSON.stringify({ wallet_address: walletAddress, signature, message }),
    },
  );
}

export async function submitFighter(
  apiKey: string,
  body: { name: string; game_id: string; character: string; model_s3_key: string },
) {
  return gatewayRequest("/submit", apiKey, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function startTraining(
  apiKey: string,
  body: { fighter_id: string; algorithm?: string; total_timesteps?: number; tier?: string },
) {
  return gatewayRequest<{ job_id: string; status: string }>("/train", apiKey, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getTrainingStatus(apiKey: string, jobId: string) {
  return gatewayRequest<{
    job_id: string;
    status: string;
    current_timesteps: number;
    total_timesteps: number;
    reward: number | null;
    error_message: string | null;
  }>(`/train/${jobId}`, apiKey);
}

export async function stopTraining(apiKey: string, jobId: string) {
  return gatewayRequest<{ job_id: string; status: string }>(
    `/train/${jobId}/stop`,
    apiKey,
    { method: "POST" },
  );
}

export async function queueForMatch(
  apiKey: string,
  body: { fighter_id: string; game_id: string; match_type?: string },
) {
  return gatewayRequest<{ queued: boolean; message: string }>("/queue", apiKey, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function createCustomMatch(
  apiKey: string,
  body: {
    fighter_a_id: string;
    fighter_b_id: string;
    match_format?: string;
    has_pool?: boolean;
  },
) {
  return gatewayRequest<{ match_id: string; game_id: string; status: string }>(
    "/match",
    apiKey,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function adoptPretrained(
  apiKey: string,
  body: { pretrained_id: string; name: string },
) {
  return gatewayRequest<{
    id: string;
    name: string;
    game_id: string;
    character: string;
    elo_rating: number;
    status: string;
  }>("/adopt", apiKey, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
