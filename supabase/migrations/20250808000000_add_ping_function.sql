-- Create a lightweight ping function for health checks
-- This avoids unnecessary table access for connection monitoring

CREATE OR REPLACE FUNCTION public.ping()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT 'pong'::text;
$$;

-- Grant execute permission to authenticated and anon users
GRANT EXECUTE ON FUNCTION public.ping() TO authenticated;
GRANT EXECUTE ON FUNCTION public.ping() TO anon;

COMMENT ON FUNCTION public.ping() IS 'Lightweight health check function that returns pong without accessing any tables';