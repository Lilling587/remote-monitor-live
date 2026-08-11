DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='storage' AND tablename='objects' AND policyname='screen_frames_public_select') THEN
    CREATE POLICY "screen_frames_public_select" ON storage.objects FOR SELECT USING (bucket_id = 'screen-frames');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='storage' AND tablename='objects' AND policyname='screen_frames_public_insert') THEN
    CREATE POLICY "screen_frames_public_insert" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'screen-frames');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='storage' AND tablename='objects' AND policyname='screen_frames_public_update') THEN
    CREATE POLICY "screen_frames_public_update" ON storage.objects FOR UPDATE USING (bucket_id = 'screen-frames') WITH CHECK (bucket_id = 'screen-frames');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='storage' AND tablename='objects' AND policyname='screen_frames_public_delete') THEN
    CREATE POLICY "screen_frames_public_delete" ON storage.objects FOR DELETE USING (bucket_id = 'screen-frames');
  END IF;
END $$;