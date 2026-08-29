-- ============================================================================
-- Migration 009: Jarvis Read-Only Ecosystem Intelligence RPCs
-- Project: pazkkzfdiwpcguoghlus (Aachman Studios Unified Supabase)
-- ============================================================================

-- 1. Get DayMentor Tasks for Target Date
CREATE OR REPLACE FUNCTION public.get_daymentor_tasks_for_date(
  p_date TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_user_id UUID;
  v_dm_data JSONB;
  v_tasks JSONB := '[]'::jsonb;
  v_filtered JSONB := '[]'::jsonb;
  v_target_date TEXT;
  v_elem JSONB;
BEGIN
  v_user_id := auth.uid();
  IF v_user_id IS NULL THEN
    RETURN jsonb_build_object('success', false, 'error', 'Authentication required.');
  END IF;

  -- Validate and normalize target date (default to today in Asia/Kolkata)
  IF p_date IS NULL OR trim(p_date) = '' THEN
    v_target_date := to_char(now() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD');
  ELSE
    BEGIN
      -- Verify valid date format
      v_target_date := to_char(p_date::date, 'YYYY-MM-DD');
    EXCEPTION WHEN OTHERS THEN
      v_target_date := to_char(now() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD');
    END;
  END IF;

  SELECT data INTO v_dm_data
  FROM public.daymentor_user_data
  WHERE user_id = v_user_id;

  IF v_dm_data IS NOT NULL AND v_dm_data ? 'tasks' THEN
    v_tasks := COALESCE(v_dm_data->'tasks', '[]'::jsonb);
    FOR v_elem IN SELECT * FROM jsonb_array_elements(v_tasks)
    LOOP
      IF (v_elem->>'deadline') = v_target_date THEN
        v_filtered := v_filtered || jsonb_build_array(v_elem);
      END IF;
    END LOOP;
  END IF;

  RETURN jsonb_build_object(
    'success', true,
    'date', v_target_date,
    'tasks', v_filtered,
    'count', jsonb_array_length(v_filtered)
  );
END;
$$;

REVOKE ALL ON FUNCTION public.get_daymentor_tasks_for_date(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_daymentor_tasks_for_date(TEXT) TO authenticated;

-- 2. Get DayMentor Next Upcoming Exam
CREATE OR REPLACE FUNCTION public.get_daymentor_next_exam()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_user_id UUID;
  v_dm_data JSONB;
  v_exams JSONB := '[]'::jsonb;
  v_next_exam JSONB := NULL;
  v_min_date TEXT := NULL;
  v_elem JSONB;
  v_exam_date TEXT;
  v_today TEXT;
BEGIN
  v_user_id := auth.uid();
  IF v_user_id IS NULL THEN
    RETURN jsonb_build_object('success', false, 'error', 'Authentication required.');
  END IF;

  v_today := to_char(now() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD');

  SELECT data INTO v_dm_data
  FROM public.daymentor_user_data
  WHERE user_id = v_user_id;

  IF v_dm_data IS NOT NULL AND v_dm_data ? 'exams' THEN
    v_exams := COALESCE(v_dm_data->'exams', '[]'::jsonb);
    FOR v_elem IN SELECT * FROM jsonb_array_elements(v_exams)
    LOOP
      v_exam_date := v_elem->>'date';
      IF v_exam_date IS NOT NULL AND v_exam_date >= v_today THEN
        IF v_min_date IS NULL OR v_exam_date < v_min_date THEN
          v_min_date := v_exam_date;
          v_next_exam := v_elem;
        END IF;
      END IF;
    END LOOP;
  END IF;

  IF v_next_exam IS NOT NULL THEN
    RETURN jsonb_build_object(
      'success', true,
      'has_exam', true,
      'exam', v_next_exam,
      'days_remaining', (to_date(v_min_date, 'YYYY-MM-DD') - to_date(v_today, 'YYYY-MM-DD'))
    );
  ELSE
    RETURN jsonb_build_object(
      'success', true,
      'has_exam', false,
      'exam', NULL
    );
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.get_daymentor_next_exam() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_daymentor_next_exam() TO authenticated;

-- 3. Get Cricket Last Match
CREATE OR REPLACE FUNCTION public.get_cricket_last_match()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_user_id UUID;
  v_match RECORD;
BEGIN
  v_user_id := auth.uid();
  IF v_user_id IS NULL THEN
    RETURN jsonb_build_object('success', false, 'error', 'Authentication required.');
  END IF;

  SELECT id, team_a, team_b, match_type, score_line, result, state, is_private, created_at
  INTO v_match
  FROM public.cricket_matches
  WHERE user_id = v_user_id
  ORDER BY created_at DESC
  LIMIT 1;

  IF v_match.id IS NOT NULL THEN
    RETURN jsonb_build_object(
      'success', true,
      'has_match', true,
      'match', jsonb_build_object(
        'id', v_match.id,
        'team_a', v_match.team_a,
        'team_b', v_match.team_b,
        'match_type', v_match.match_type,
        'score_line', v_match.score_line,
        'result', v_match.result,
        'completed', COALESCE((v_match.state->>'completed')::boolean, false),
        'created_at', v_match.created_at
      )
    );
  ELSE
    RETURN jsonb_build_object(
      'success', true,
      'has_match', false,
      'match', NULL
    );
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.get_cricket_last_match() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_cricket_last_match() TO authenticated;

-- 4. Get Hackathon Latest Result (Completed simulations only)
CREATE OR REPLACE FUNCTION public.get_hackathon_latest_result()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_user_id UUID;
  v_act RECORD;
BEGIN
  v_user_id := auth.uid();
  IF v_user_id IS NULL THEN
    RETURN jsonb_build_object('success', false, 'error', 'Authentication required.');
  END IF;

  -- Strictly filter for simulation_completed (NOT simulation_started)
  SELECT id, title, subtitle, metadata, occurred_at
  INTO v_act
  FROM public.user_activity
  WHERE user_id = v_user_id
    AND app_id = 'hackathon_simulator'
    AND activity_type = 'simulation_completed'
  ORDER BY occurred_at DESC
  LIMIT 1;

  IF v_act.id IS NOT NULL THEN
    RETURN jsonb_build_object(
      'success', true,
      'has_result', true,
      'result', jsonb_build_object(
        'title', v_act.title,
        'subtitle', v_act.subtitle,
        'score', COALESCE((v_act.metadata->>'score')::int, (v_act.metadata->>'finalScore')::int, NULL),
        'problem_title', COALESCE(v_act.metadata->>'problemTitle', v_act.title),
        'difficulty', COALESCE(v_act.metadata->>'difficulty', 'medium'),
        'completed_at', v_act.occurred_at
      )
    );
  ELSE
    RETURN jsonb_build_object(
      'success', true,
      'has_result', false,
      'result', NULL
    );
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.get_hackathon_latest_result() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_hackathon_latest_result() TO authenticated;
