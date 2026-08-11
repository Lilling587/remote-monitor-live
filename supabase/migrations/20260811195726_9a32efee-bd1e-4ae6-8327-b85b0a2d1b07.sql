CREATE POLICY "Public can read screen frames" ON storage.objects FOR SELECT USING (bucket_id = 'screen-frames');
CREATE POLICY "Host can upload screen frames" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'screen-frames');
CREATE POLICY "Host can update screen frames" ON storage.objects FOR UPDATE USING (bucket_id = 'screen-frames') WITH CHECK (bucket_id = 'screen-frames');