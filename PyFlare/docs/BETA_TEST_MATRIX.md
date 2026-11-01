# PyFlare OS — Beta 1.0 Test Matrix

**Document Status:** QA & Test Execution Standard  
**Release Target:** 2 February 2027  
**Test Suite Location:** `PyFlare/control_plane/tests/` and `PyFlare/validation/`  

---

## 1. Test Suite Classification

| Suite | Scope | Execution Command | Current Status | Passing / Total |
|---|---|---|---|---|
| **Control Plane Unit & Acceptance** | Auth, Router, Engine, Hardware, Context, Model Registry | `pytest PyFlare/control_plane/tests` | **PASS** | 78 / 78 |
| **Live Unity 6 Vertical Slice** | Batchmode Unity 6 bridge automation & execution engine | `pytest PyFlare/control_plane/tests/test_live_unity_integration.py` | **PASS** | 1 / 1 |
| **VirtualBox Low-Memory Performance** | Grids of boot, memory, zram, and schema settings | `pytest PyFlare/control_plane/tests/test_performance_optimizations.py` | **PASS** | 7 / 7 |
| **Asset & Icon Validation** | PyFlare themes, icons, cursors, and desktop files | `python PyFlare/validation/validate_icons.py` | **PASS** | Verified |
| **JSON & Schema Integrity** | TaskSpec schemas, model registry JSON, installer config | `python PyFlare/validation/validate_json.py` | **PASS** | Verified |
| **ISO Assembly Pipeline** | Remaster squashfs, initrd patching, xorriso assembly | `python PyFlare/scripts/fix_and_build_iso.py` | **PASS** | 2.86 GB ISO |
| **End-to-End Hypervisor Boot** | VirtualBox headless/GUI boot to GNOME desktop | `VBoxManage startvm Pyflare` | **IN PROGRESS** | Validating GUI |

---

## 2. Hardware & Hypervisor Target Matrix

| Target Environment | vCPUs | RAM | Graphics Controller | Primary Test Objective | Gate Requirement |
|---|---|---|---|---|---|
| **VirtualBox 7.x (Minimum Spec)** | 2 | 4096 MB | VMSVGA (128 MB, 3D Enabled) | Verify low-memory stability, boot < 45s, ZRAM swap activation. | **Gate 1, Gate 7 (Mandatory)** |
| **VirtualBox 7.x (Constrained Spec)**| 2 | 2048 MB | VMSVGA (64 MB, 3D Disabled) | Verify graceful degradation, API-only model tier, OOM avoidance. | **Gate 2, Gate 7 (Stress)** |
| **VirtualBox 7.x (Recommended Spec)**| 4 | 8192 MB | VMSVGA (256 MB, 3D Enabled) | Verify local small language model execution, desktop fluidity. | **Gate 2, Gate 6** |
| **QEMU / KVM** | 2 | 4096 MB | VirtIO-GPU / std vga | Verify hypervisor neutrality and non-VirtualBox boot compatibility. | **Gate 1** |
| **Bare-Metal x86_64 Reference** | 8 | 16384 MB | NVIDIA RTX / Intel Arc | Verify discrete GPU detection, full local model tier, Unity 6 GUI. | **Gate 2, Gate 6** |

---

## 3. Automated Test Inventory (78 Acceptance Tests)

```
tests/test_auth.py:
  ✓ test_acceptance_1_registration_login_logout
  ✓ test_acceptance_2_authentication_failures_handled_explicitly
  ✓ test_acceptance_3_expired_session_handling
  ✓ test_acceptance_4_secure_provider_credentials_storage_and_separation
  ✓ test_acceptance_5_secret_sanitizer_redacts_keys_from_logs_and_errors
  ✓ test_acceptance_6_offline_operation_preservation

tests/test_cli.py:
  ✓ test_cli_auth_flow
  ✓ test_cli_context_flow
  ✓ test_cli_hardware
  ✓ test_cli_models_list
  ✓ test_cli_models_recommend
  ✓ test_cli_models_recommend_api_only

tests/test_codec.py:
  ✓ test_boolean_is_not_accepted_as_integer
  ✓ test_local_only_cannot_enable_cloud
  ✓ test_round_trip_is_stable
  ✓ test_unknown_fields_are_rejected

tests/test_context_manager.py:
  ✓ test_acceptance_1_index_representative_unity_project
  ✓ test_acceptance_2_and_3_ask_question_and_retrieve_relevant_source
  ✓ test_acceptance_4_file_change_reflected_in_refreshed_context
  ✓ test_acceptance_5_project_isolation
  ✓ test_acceptance_6_excluded_secrets_never_included
  ✓ test_acceptance_7_predictable_behavior_when_stale_or_empty

tests/test_execution_engine.py:
  ✓ test_acceptance_1_and_8_valid_task_completes_and_displays
  ✓ test_acceptance_2_invalid_task_is_rejected
  ✓ test_acceptance_3_disconnected_editor_actionable_error
  ✓ test_acceptance_4_unauthorized_task_blocked
  ✓ test_acceptance_5_validation_detects_unsuccessful_operation
  ✓ test_acceptance_6_audit_log_records_request_route_and_results
  ✓ test_acceptance_7_retrying_task_is_idempotent_no_duplicate

tests/test_firstboot.py:
  ✓ test_default_first_boot_flow
  ✓ test_first_boot_api_only_choice
  ✓ test_first_boot_idempotency_and_recovery
  ✓ test_first_boot_with_provider_credentials

tests/test_live_unity_integration.py:
  ✓ test_live_unity_end_to_end_vertical_slice

tests/test_model_registry.py:
  ✓ test_acceptance_1_hardware_detection_structured_report
  ✓ test_acceptance_2_missing_gpu_handled_safely
  ✓ test_acceptance_3_recommendations_respect_memory_and_storage
  ✓ test_acceptance_4_insufficient_storage_blocks_download_before_start
  ✓ test_acceptance_5_invalid_model_metadata_rejected
  ✓ test_acceptance_6_user_can_select_api_only
  ✓ test_acceptance_7_model_download_integrity_verification

tests/test_performance_optimizations.py:
  ✓ test_cache_invalidation_works_cleanly
  ✓ test_firstboot_defers_model_downloads
  ✓ test_gnome_overrides_exclude_blur_my_shell
  ✓ test_grub_default_boot_omits_nomodeset
  ✓ test_hardware_caching_latency_reduction
  ✓ test_systemd_engine_service_avoids_dbus_blocking_timeout
  ✓ test_systemd_session_service_has_condition_path

tests/test_router.py:
  ✓ test_circuit_breaker_and_unavailable_provider_fallback
  ✓ test_cloud_is_hard_filtered_when_disallowed
  ✓ test_deterministic_reproducibility_same_inputs_same_route
  ✓ test_deterministic_tool_beats_unnecessary_cloud_model
  ✓ test_insufficient_resources_produces_structured_explanation
  ✓ test_offline_state_removes_cloud_route
  ✓ test_unauthorized_task_never_routes

tests/test_scheduler.py:
  ✓ test_admits_with_headroom
  ✓ test_preempts_only_lower_priority_preemptible_work

tests/test_security.py:
  ✓ test_path_scope_enforces_root_allowlist_and_denylist

tests/test_unity_client.py:
  ✓ test_execute_round_trip
  ✓ test_health_is_authenticated
  ✓ test_mismatched_response_is_rejected
  ✓ test_non_loopback_endpoint_is_rejected
  ✓ test_oversized_response_is_rejected
  ✓ test_short_token_is_rejected

tests/test_unity_package_contract.py:
  ✓ test_bridge_keeps_foundation_security_boundaries
  ✓ test_idempotency_store_does_not_reference_bridge_secret
  ✓ test_manifest_is_a_valid_editor_package

tests/test_unity_protocol.py:
  ✓ test_accepts_matching_idle_editor
  ✓ test_rejects_stale_or_busy_editor

tests/test_validation_retry.py:
  ✓ test_all_required_validators_must_pass
  ✓ test_permission_failure_never_auto_retries
  ✓ test_repeated_identical_failure_opens_escalation
  ✓ test_skipped_required_validator_is_not_pass

tests/test_workflow_journal.py:
  ✓ test_durable_transitions_and_events
  ✓ test_idempotency_reservation_replays_completed_result
  ✓ test_invalid_transition_is_rejected
  ✓ test_stale_revision_is_rejected
  ✓ test_workflow_rejects_cycles_and_reports_ready_steps
```
