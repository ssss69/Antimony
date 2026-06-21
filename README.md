# Antimony

## Hosted deployment

The frontend deploys to Vercel and the Python API deploys separately to Render.
`/api/config` gives the browser the public runtime configuration it needs.

Set this Vercel environment variable if the Render URL differs from the default:

```text
ANTIMONY_API_URL=https://your-antimony-api.onrender.com
```

Keep `SUPABASE_SERVICE_ROLE_KEY` out of Vercel. Configure `SUPABASE_URL` and
`SUPABASE_ANON_KEY` on the Render service; the browser retrieves those public
values through the API. Run `supabase_schema.sql` once in Supabase's SQL editor
to create the tables and apply the idempotent RLS policy hardening.

### Supabase sign-in providers

- Google: enable the Google provider in Supabase Authentication, add its Google
  client ID and secret, and use the Supabase callback URL shown in that panel.
- Keep the Site URL set to `https://antimony-seven.vercel.app` and allow
  `https://antimony-seven.vercel.app/**` as a redirect URL.
