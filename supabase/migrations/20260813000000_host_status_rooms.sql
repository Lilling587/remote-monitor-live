-- Add a room column to host_status so each stage has its own status row
ALTER TABLE public.host_status ADD COLUMN IF NOT EXISTS room TEXT NOT NULL DEFAULT 'default';

-- Drop the single-row constraint so we can have one row per room
ALTER TABLE public.host_status DROP CONSTRAINT IF EXISTS host_status_single_row;

-- Change primary key from id=1 to room name
ALTER TABLE public.host_status DROP CONSTRAINT IF EXISTS host_status_pkey;
ALTER TABLE public.host_status ADD PRIMARY KEY (room);

-- Insert rows for our two stages
INSERT INTO public.host_status (id, room, is_connected)
VALUES (2, 'stora-salen', false), (3, 'blackbox', false)
ON CONFLICT (room) DO NOTHING;

-- Update the RLS policy to match on room instead of id=1
DROP POLICY IF EXISTS "host_status_public_update" ON public.host_status;
CREATE POLICY "host_status_public_update" ON public.host_status
  FOR UPDATE TO anon, authenticated
  USING (true)
  WITH CHECK (true);
