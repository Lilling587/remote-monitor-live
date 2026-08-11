DROP POLICY IF EXISTS "screen_frames_public_read" ON storage.objects;
DROP POLICY IF EXISTS "screen_frames_public_insert" ON storage.objects;
DROP POLICY IF EXISTS "screen_frames_public_update" ON storage.objects;
DROP POLICY IF EXISTS "screen_frames_public_delete" ON storage.objects;

CREATE POLICY "screen_frames_public_read" ON storage.objects
  FOR SELECT TO anon, authenticated
  USING (bucket_id = 'screen-frames');

CREATE POLICY "screen_frames_public_insert" ON storage.objects
  FOR INSERT TO anon, authenticated
  WITH CHECK (bucket_id = 'screen-frames');

CREATE POLICY "screen_frames_public_update" ON storage.objects
  FOR UPDATE TO anon, authenticated
  USING (bucket_id = 'screen-frames')
  WITH CHECK (bucket_id = 'screen-frames');

CREATE POLICY "screen_frames_public_delete" ON storage.objects
  FOR DELETE TO anon, authenticated
  USING (bucket_id = 'screen-frames');

CREATE TABLE public.host_status (
  id INTEGER PRIMARY KEY DEFAULT 1,
  last_seen_at TIMESTAMPTZ,
  is_connected BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT host_status_single_row CHECK (id = 1)
);

GRANT SELECT, UPDATE ON public.host_status TO anon;
GRANT SELECT, UPDATE ON public.host_status TO authenticated;
GRANT ALL ON public.host_status TO service_role;

ALTER TABLE public.host_status ENABLE ROW LEVEL SECURITY;

CREATE POLICY "host_status_public_read" ON public.host_status
  FOR SELECT TO anon, authenticated
  USING (true);

CREATE POLICY "host_status_public_update" ON public.host_status
  FOR UPDATE TO anon, authenticated
  USING (id = 1)
  WITH CHECK (id = 1);

INSERT INTO public.host_status (id, is_connected) VALUES (1, false);

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public;

CREATE TRIGGER update_host_status_updated_at
  BEFORE UPDATE ON public.host_status
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.host_status REPLICA IDENTITY FULL;
ALTER PUBLICATION supabase_realtime ADD TABLE public.host_status;