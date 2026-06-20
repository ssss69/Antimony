function validHttpsUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.origin : "";
  } catch {
    return "";
  }
}

export default function handler(_request, response) {
  const apiUrl = validHttpsUrl(
    process.env.ANTIMONY_API_URL || "https://antimony-ai.onrender.com",
  );
  const supabaseUrl = validHttpsUrl(process.env.SUPABASE_URL);
  const anonKey = process.env.SUPABASE_ANON_KEY || "";

  // Only public browser configuration belongs here. Never add a service-role key.
  const config = {
    apiUrl,
    supabaseUrl,
    supabaseAnonKey: anonKey,
  };

  response.setHeader("Content-Type", "application/javascript; charset=utf-8");
  response.setHeader("Cache-Control", "no-store, max-age=0");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.status(200).send(
    `window.ANTIMONY_CONFIG=${JSON.stringify(config)};` +
    `window.ANTIMONY_API=window.ANTIMONY_CONFIG.apiUrl||window.ANTIMONY_API;`,
  );
}
