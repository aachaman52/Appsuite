-- ============================================================================
-- Migration 010: Ecosystem Action Idempotency Hardening
-- Project: pazkkzfdiwpcguoghlus (Aachman Studios Unified Supabase)
-- ============================================================================

-- 1. Add idempotency_key column to public.ecosystem_commands
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' 
      AND table_name = 'ecosystem_commands' 
      AND column_name = 'idempotency_key'
  ) THEN
    ALTER TABLE public.ecosystem_commands ADD COLUMN idempotency_key TEXT;
  END IF;
END $$;

-- 2. Create partial unique index on (user_id, idempotency_key)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ecosystem_commands_user_idempotency 
ON public.ecosystem_commands(user_id, idempotency_key) 
WHERE idempotency_key IS NOT NULL;

-- 3. Update public.execute_ecosystem_action RPC with idempotency key handling
CREATE OR REPLACE FUNCTION public.execute_ecosystem_action(
  p_action_type TEXT,
  p_payload JSONB DEFAULT '{}'::jsonb,
  p_idempotency_key TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_user_id UUID;
  v_target_app TEXT;
  v_command_id UUID;
  v_existing_id UUID;
  v_existing_status TEXT;
  v_existing_result JSONB;
  v_existing_err TEXT;
  v_entity_id TEXT;
  v_deep_link TEXT;
  v_result JSONB;
  
  -- DayMentor task variables
  v_task_title TEXT;
  v_task_subject TEXT;
  v_task_deadline TEXT;
  v_task_priority TEXT;
  v_task_difficulty TEXT;
  v_task_id TEXT;
  v_task_obj JSONB;
  v_dm_current_data JSONB;
  v_dm_tasks JSONB;

  -- Cricket match variables
  v_team_a TEXT;
  v_team_b TEXT;
  v_match_type TEXT;
  v_overs INT;
  v_match_id TEXT;
  v_match_state JSONB;

  -- Hackathon simulation variables
  v_problem_id TEXT;
  v_problem_title TEXT;
  v_difficulty TEXT;
  v_run_id TEXT;
BEGIN
  v_user_id := auth.uid();
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Authentication required to execute ecosystem actions.';
  END IF;

  -- Allowlist validation
  IF p_action_type NOT IN (
    'daymentor.create_task',
    'cricket_scorer.create_match',
    'hackathon_simulator.start_simulation'
  ) THEN
    -- Log failed attempt
    INSERT INTO public.ecosystem_commands (user_id, target_app, action_type, payload, status, error_message, idempotency_key)
    VALUES (v_user_id, 'unknown', p_action_type, p_payload, 'failed', 'Unsupported action type', p_idempotency_key);

    RETURN jsonb_build_object(
      'success', false,
      'error', 'Unsupported ecosystem action type: ' || COALESCE(p_action_type, 'null')
    );
  END IF;

  -- Set target app name
  IF p_action_type = 'daymentor.create_task' THEN
    v_target_app := 'daymentor';
  ELSIF p_action_type = 'cricket_scorer.create_match' THEN
    v_target_app := 'cricket_scorer';
  ELSIF p_action_type = 'hackathon_simulator.start_simulation' THEN
    v_target_app := 'hackathon_simulator';
  END IF;

  -- ── Idempotency Check ─────────────────────────────────────────────────────
  IF p_idempotency_key IS NOT NULL AND trim(p_idempotency_key) <> '' THEN
    SELECT id, status, result, error_message
    INTO v_existing_id, v_existing_status, v_existing_result, v_existing_err
    FROM public.ecosystem_commands
    WHERE user_id = v_user_id AND idempotency_key = p_idempotency_key;

    IF v_existing_id IS NOT NULL THEN
      IF v_existing_status = 'completed' THEN
        -- Return identical stored result without repeating target mutation
        RETURN v_existing_result;
      ELSIF v_existing_status = 'pending' THEN
        RETURN jsonb_build_object(
          'success', false,
          'status', 'pending',
          'message', 'Command execution in progress. Please retry shortly.'
        );
      ELSE
        RETURN jsonb_build_object(
          'success', false,
          'error', COALESCE(v_existing_err, 'Command previously failed.')
        );
      END IF;
    END IF;

    -- Claim command row in 'pending' state
    BEGIN
      INSERT INTO public.ecosystem_commands (
        user_id, target_app, action_type, payload, status, idempotency_key, created_at, completed_at
      ) VALUES (
        v_user_id, v_target_app, p_action_type, p_payload, 'pending', p_idempotency_key, now(), now()
      ) RETURNING id INTO v_command_id;
    EXCEPTION WHEN unique_violation THEN
      -- Concurrent request claimed the key in parallel
      SELECT id, status, result, error_message
      INTO v_existing_id, v_existing_status, v_existing_result, v_existing_err
      FROM public.ecosystem_commands
      WHERE user_id = v_user_id AND idempotency_key = p_idempotency_key;

      IF v_existing_status = 'completed' THEN
        RETURN v_existing_result;
      ELSE
        RETURN jsonb_build_object(
          'success', false,
          'status', 'pending',
          'message', 'Command execution in progress. Please retry shortly.'
        );
      END IF;
    END;
  ELSE
    -- No idempotency key provided
    INSERT INTO public.ecosystem_commands (
      user_id, target_app, action_type, payload, status, created_at, completed_at
    ) VALUES (
      v_user_id, v_target_app, p_action_type, p_payload, 'pending', now(), now()
    ) RETURNING id INTO v_command_id;
  END IF;

  -- ─── 1. DayMentor: Create Task ──────────────────────────────────────────
  IF p_action_type = 'daymentor.create_task' THEN
    v_task_title := trim(COALESCE(p_payload->>'title', ''));
    v_task_subject := COALESCE(p_payload->>'subject_id', '');
    v_task_deadline := COALESCE(p_payload->>'deadline', '');
    v_task_priority := COALESCE(p_payload->>'priority', 'medium');
    v_task_difficulty := COALESCE(p_payload->>'difficulty', 'medium');

    IF length(v_task_title) = 0 THEN
      UPDATE public.ecosystem_commands SET status = 'failed', error_message = 'Task title cannot be empty.' WHERE id = v_command_id;
      RETURN jsonb_build_object('success', false, 'error', 'Task title cannot be empty.');
    END IF;
    IF length(v_task_title) > 200 THEN
      UPDATE public.ecosystem_commands SET status = 'failed', error_message = 'Task title exceeds maximum allowed length.' WHERE id = v_command_id;
      RETURN jsonb_build_object('success', false, 'error', 'Task title exceeds maximum allowed length of 200 characters.');
    END IF;
    IF v_task_priority NOT IN ('low', 'medium', 'high') THEN
      v_task_priority := 'medium';
    END IF;
    IF v_task_difficulty NOT IN ('easy', 'medium', 'hard') THEN
      v_task_difficulty := 'medium';
    END IF;

    v_task_id := 'task_' || replace(gen_random_uuid()::text, '-', '');
    v_task_obj := jsonb_build_object(
      'id', v_task_id,
      'title', v_task_title,
      'subjectId', v_task_subject,
      'deadline', v_task_deadline,
      'duration', 30,
      'difficulty', v_task_difficulty,
      'priority', v_task_priority,
      'completed', false,
      'createdAt', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
    );

    SELECT data INTO v_dm_current_data
    FROM public.daymentor_user_data
    WHERE user_id = v_user_id;

    IF v_dm_current_data IS NULL THEN
      v_dm_current_data := jsonb_build_object(
        'tasks', jsonb_build_array(v_task_obj),
        'subjects', '[]'::jsonb,
        'exams', '[]'::jsonb,
        'focusSessions', '[]'::jsonb,
        'streak', jsonb_build_object('current', 0, 'best', 0, 'lastActiveDate', '')
      );

      INSERT INTO public.daymentor_user_data (user_id, data, updated_at)
      VALUES (v_user_id, v_dm_current_data, now());
    ELSE
      v_dm_tasks := COALESCE(v_dm_current_data->'tasks', '[]'::jsonb);
      v_dm_tasks := v_dm_tasks || jsonb_build_array(v_task_obj);
      v_dm_current_data := jsonb_set(v_dm_current_data, '{tasks}', v_dm_tasks);

      UPDATE public.daymentor_user_data
      SET data = v_dm_current_data, updated_at = now()
      WHERE user_id = v_user_id;
    END IF;

    v_entity_id := v_task_id;
    v_deep_link := 'https://daymentor.vercel.app/tasks';

    PERFORM public.record_user_activity(
      p_app_id := 'daymentor',
      p_activity_type := 'task_created',
      p_title := 'Created task: ' || v_task_title,
      p_subtitle := 'Priority: ' || initcap(v_task_priority) || CASE WHEN v_task_deadline <> '' THEN ' • Due: ' || v_task_deadline ELSE '' END,
      p_metadata := jsonb_build_object('taskId', v_task_id, 'priority', v_task_priority, 'deadline', v_task_deadline, 'source', 'ecosystem_action'),
      p_action_url := v_deep_link,
      p_event_key := 'daymentor_task_' || v_task_id
    );

  -- ─── 2. Cricket Scorer: Create Match ─────────────────────────────────────
  ELSIF p_action_type = 'cricket_scorer.create_match' THEN
    v_team_a := trim(COALESCE(p_payload->>'team_a', ''));
    v_team_b := trim(COALESCE(p_payload->>'team_b', ''));
    v_match_type := COALESCE(p_payload->>'match_type', 'T20');
    v_overs := COALESCE((p_payload->>'overs')::int, 20);

    IF length(v_team_a) = 0 OR length(v_team_b) = 0 THEN
      UPDATE public.ecosystem_commands SET status = 'failed', error_message = 'Both Team A and Team B names are required.' WHERE id = v_command_id;
      RETURN jsonb_build_object('success', false, 'error', 'Both Team A and Team B names are required.');
    END IF;
    IF v_overs <= 0 OR v_overs > 100 THEN
      v_overs := 20;
    END IF;

    v_match_id := 'match_' || replace(gen_random_uuid()::text, '-', '');
    v_match_state := jsonb_build_object(
      'id', v_match_id,
      'teamA', v_team_a,
      'teamB', v_team_b,
      'overs', v_overs,
      'matchType', v_match_type,
      'completed', false,
      'createdAt', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
    );

    INSERT INTO public.cricket_matches (
      id, user_id, date, team_a, team_b, match_type, score_line, result, state, is_private, created_at, updated_at
    ) VALUES (
      v_match_id,
      v_user_id,
      (extract(epoch from now()) * 1000)::bigint,
      v_team_a,
      v_team_b,
      v_match_type,
      v_team_a || ' vs ' || v_team_b,
      '{}'::jsonb,
      v_match_state,
      false,
      now(),
      now()
    );

    v_entity_id := v_match_id;
    v_deep_link := 'https://cricket-scorer.vercel.app/match/' || v_match_id;

    PERFORM public.record_user_activity(
      p_app_id := 'cricket_scorer',
      p_activity_type := 'match_created',
      p_title := 'New Match: ' || v_team_a || ' vs ' || v_team_b,
      p_subtitle := v_match_type || ' • ' || v_overs || ' Overs',
      p_metadata := jsonb_build_object('matchId', v_match_id, 'teamA', v_team_a, 'teamB', v_team_b, 'overs', v_overs, 'matchType', v_match_type, 'source', 'ecosystem_action'),
      p_action_url := v_deep_link,
      p_event_key := 'cricket_match_' || v_match_id
    );

  -- ─── 3. Hackathon Simulator: Start Simulation ────────────────────────────
  ELSIF p_action_type = 'hackathon_simulator.start_simulation' THEN
    v_problem_id := COALESCE(p_payload->>'problem_id', 'prob-learnflow');
    v_problem_title := COALESCE(p_payload->>'problem_title', 'LearnFlow AI');
    v_difficulty := COALESCE(p_payload->>'difficulty', 'medium');

    v_run_id := 'sim_' || replace(gen_random_uuid()::text, '-', '');
    v_entity_id := v_run_id;
    v_deep_link := 'https://the-hackathon-simulator.vercel.app/game?problem=' || v_problem_id || '&simId=' || v_run_id;

    PERFORM public.record_user_activity(
      p_app_id := 'hackathon_simulator',
      p_activity_type := 'simulation_started',
      p_title := 'Started Simulation: ' || v_problem_title,
      p_subtitle := 'Difficulty: ' || initcap(v_difficulty),
      p_metadata := jsonb_build_object('simId', v_run_id, 'problemId', v_problem_id, 'problemTitle', v_problem_title, 'difficulty', v_difficulty, 'source', 'ecosystem_action'),
      p_action_url := v_deep_link,
      p_event_key := 'hackathon_sim_' || v_run_id
    );
  END IF;

  v_result := jsonb_build_object(
    'success', true,
    'command_id', v_command_id,
    'action_type', p_action_type,
    'entity_id', v_entity_id,
    'deep_link', v_deep_link,
    'timestamp', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
  );

  UPDATE public.ecosystem_commands
  SET status = 'completed',
      result = v_result,
      completed_at = now()
  WHERE id = v_command_id;

  RETURN v_result;
END;
$$;

REVOKE ALL ON FUNCTION public.execute_ecosystem_action(TEXT, JSONB, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.execute_ecosystem_action(TEXT, JSONB, TEXT) TO authenticated;
