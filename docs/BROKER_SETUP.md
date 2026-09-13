# Broker access for the synthetic demo

Member and broker reviews use separate Supabase Auth accounts. A broker role alone does not grant access to any case: an administrator must also assign the member account to that broker. Members and brokers cannot create their own assignments through the application.

1. Create or sign up two accounts in the local Supabase instance: one member and one broker. Find their UUIDs in Supabase Studio under **Authentication → Users**.
2. From a trusted administrator SQL session, replace the placeholders below with those UUIDs. Do not run this SQL with a member's or broker's browser credentials.

```sql
UPDATE auth.users
SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || '{"helm_role":"broker"}'::jsonb
WHERE id = '<broker-user-uuid>'::uuid;

INSERT INTO public.broker_assignments (member_id, broker_id)
VALUES ('<member-user-uuid>', '<broker-user-uuid>')
ON CONFLICT (member_id) DO UPDATE SET broker_id = EXCLUDED.broker_id;
```

3. Sign in as the member to prepare a recommendation or submit an appeal. Sign in separately as the broker to review assigned cases. The member's application will accept a confirmation only after the broker has reviewed the recommendation.

The backend validates every bearer token with Supabase Auth and reads `helm_role` only from administrator-controlled `app_metadata`. It checks `broker_assignments` for each broker queue and detail action. The assignment table denies direct access to `anon` and `authenticated`; only trusted server/database administration should change it. Reassigning a member removes the previous broker's case access immediately.
