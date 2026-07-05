from __future__ import annotations
import uuid
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from .semantic_memory.embedding_client import EmbeddingClient
from ..logging_setup import get_logger

log = get_logger("core.project_manager")

class ProjectHierarchyNode:
    """Represents a node in the vision-to-task project hierarchy."""
    def __init__(self, node_id: str, project_id: str, parent_id: Optional[str],
                 node_type: str, name: str, status: str = "pending",
                 estimated_duration: float = 0.0, actual_duration: float = 0.0,
                 dependencies: List[str] = None, metadata: Dict[str, Any] = None):
        self.id = node_id
        self.project_id = project_id
        self.parent_id = parent_id
        self.node_type = node_type # 'vision' | 'project' | 'milestone' | 'epic' | 'feature' | 'task' | 'subtask'
        self.name = name
        self.status = status # 'pending' | 'running' | 'completed' | 'failed' | 'blocked'
        self.estimated_duration = estimated_duration
        self.actual_duration = actual_duration
        self.dependencies = dependencies or []
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "parent_id": self.parent_id,
            "node_type": self.node_type,
            "name": self.name,
            "status": self.status,
            "estimated_duration": self.estimated_duration,
            "actual_duration": self.actual_duration,
            "dependencies": self.dependencies,
            "metadata": self.metadata
        }

class ProjectManager:
    """Manages the autonomous project management lifecycle and hierarchy DAG."""
    def __init__(self, db: Any, brain: Any = None):
        self.db = db
        self.brain = brain
        self.embedding_client = EmbeddingClient(db)

    def load_templates(self) -> List[Dict[str, Any]]:
        """Load templates from config/templates.json."""
        config_path = Path(__file__).resolve().parent.parent.parent / "config" / "templates.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    return json.load(f).get("templates", [])
            except Exception as e:
                log.warning("Failed to load templates: %s", e)
        return []

    def select_best_template(self, goal: str) -> Dict[str, Any]:
        """Selects the best matching template using semantic similarity of keywords and names."""
        templates = self.load_templates()
        if not templates:
            return {
                "id": "generic_scene",
                "name": "Generic Scene",
                "asset_slots": [{ "role": "prop", "count": 8, "search_terms": ["prop"] }]
            }

        goal_emb = self.embedding_client.get_embedding(goal)
        best_template = None
        best_score = -1.0

        for t in templates:
            # Combine template name and keywords for comparison
            keywords_str = " ".join(t.get("keywords", []))
            template_text = f"{t.get('name', '')} {keywords_str}"
            temp_emb = self.embedding_client.get_embedding(template_text)
            score = EmbeddingClient.cosine_similarity(goal_emb, temp_emb)
            
            log.info("Template %s similarity score: %f", t.get("name"), score)
            if score > best_score:
                best_score = score
                best_template = t

        # If score is too low or no template found, default to generic scene
        if not best_template or best_score < 0.15:
            log.info("Low similarity, defaulting to generic template")
            best_template = next((t for t in templates if t.get("id") == "generic_scene"), templates[0])

        return best_template

    def create_project_plan(self, project_id: str, goal: str) -> List[ProjectHierarchyNode]:
        """Generate and store the vision-to-task hierarchy DAG in the database."""
        template = self.select_best_template(goal)
        log.info("Selected template %s for project %s", template.get("name"), project_id)

        nodes: List[ProjectHierarchyNode] = []
        
        # 1. Vision Node
        vision_id = f"vision_{uuid.uuid4().hex[:8]}"
        vision_node = ProjectHierarchyNode(
            node_id=vision_id,
            project_id=project_id,
            parent_id=None,
            node_type="vision",
            name=f"Vision: {goal}",
            status="pending"
        )
        nodes.append(vision_node)

        # 2. Project Node
        project_node_id = f"proj_{uuid.uuid4().hex[:8]}"
        project_node = ProjectHierarchyNode(
            node_id=project_node_id,
            project_id=project_id,
            parent_id=vision_id,
            node_type="project",
            name=f"Project: {template.get('name')}",
            status="pending",
            metadata={"template": template}
        )
        nodes.append(project_node)

        # 3. Milestones, Epics, Features, Tasks
        # Milestone 1: Asset Sourcing
        m1_id = f"m1_{uuid.uuid4().hex[:8]}"
        m1_node = ProjectHierarchyNode(
            node_id=m1_id,
            project_id=project_id,
            parent_id=project_node_id,
            node_type="milestone",
            name="Milestone 1: Asset Sourcing",
            status="pending"
        )
        nodes.append(m1_node)

        epic1_id = f"epic1_{uuid.uuid4().hex[:8]}"
        epic1_node = ProjectHierarchyNode(
            node_id=epic1_id,
            project_id=project_id,
            parent_id=m1_id,
            node_type="epic",
            name="Epic: Gather Asset Library",
            status="pending"
        )
        nodes.append(epic1_node)

        # Create asset sourcing features and tasks for each slot
        asset_slots = template.get("asset_slots", [])
        m1_tasks = []
        for slot in asset_slots:
            feat_id = f"feat_src_{slot['role']}_{uuid.uuid4().hex[:4]}"
            feat_node = ProjectHierarchyNode(
                node_id=feat_id,
                project_id=project_id,
                parent_id=epic1_id,
                node_type="feature",
                name=f"Feature: Source {slot['role']}",
                status="pending"
            )
            nodes.append(feat_node)

            task_id = f"task_src_{slot['role']}_{uuid.uuid4().hex[:4]}"
            task_node = ProjectHierarchyNode(
                node_id=task_id,
                project_id=project_id,
                parent_id=feat_id,
                node_type="task",
                name=f"Task: Source assets for {slot['role']}",
                status="pending",
                metadata={"agent": "asset", "role": slot["role"], "search_terms": slot.get("search_terms", [])}
            )
            self.estimate_complexity_and_duration(task_node)
            nodes.append(task_node)
            m1_tasks.append(task_id)

        # Milestone 2: Optimization
        m2_id = f"m2_{uuid.uuid4().hex[:8]}"
        m2_node = ProjectHierarchyNode(
            node_id=m2_id,
            project_id=project_id,
            parent_id=project_node_id,
            node_type="milestone",
            name="Milestone 2: Optimization & Preparation",
            status="pending",
            dependencies=[m1_id]
        )
        nodes.append(m2_node)

        epic2_id = f"epic2_{uuid.uuid4().hex[:8]}"
        epic2_node = ProjectHierarchyNode(
            node_id=epic2_id,
            project_id=project_id,
            parent_id=m2_id,
            node_type="epic",
            name="Epic: Blender Model Optimization",
            status="pending",
            dependencies=[epic1_id]
        )
        nodes.append(epic2_node)

        m2_tasks = []
        for slot in asset_slots:
            feat_id = f"feat_opt_{slot['role']}_{uuid.uuid4().hex[:4]}"
            feat_node = ProjectHierarchyNode(
                node_id=feat_id,
                project_id=project_id,
                parent_id=epic2_id,
                node_type="feature",
                name=f"Feature: Optimize {slot['role']}",
                status="pending"
            )
            nodes.append(feat_node)

            task_id = f"task_opt_{slot['role']}_{uuid.uuid4().hex[:4]}"
            # Depends on the source task completing
            src_task_id = next((t_id for t_id in m1_tasks if slot["role"] in t_id), None)
            dependencies = [src_task_id] if src_task_id else []

            task_node = ProjectHierarchyNode(
                node_id=task_id,
                project_id=project_id,
                parent_id=feat_id,
                node_type="task",
                name=f"Task: Optimize meshes for {slot['role']}",
                status="pending",
                dependencies=dependencies,
                metadata={"agent": "blender", "role": slot["role"]}
            )
            self.estimate_complexity_and_duration(task_node)
            nodes.append(task_node)
            m2_tasks.append(task_id)

        # Milestone 3: Assembly
        m3_id = f"m3_{uuid.uuid4().hex[:8]}"
        m3_node = ProjectHierarchyNode(
            node_id=m3_id,
            project_id=project_id,
            parent_id=project_node_id,
            node_type="milestone",
            name="Milestone 3: Scene Construction",
            status="pending",
            dependencies=[m2_id]
        )
        nodes.append(m3_node)

        epic3_id = f"epic3_{uuid.uuid4().hex[:8]}"
        epic3_node = ProjectHierarchyNode(
            node_id=epic3_id,
            project_id=project_id,
            parent_id=m3_id,
            node_type="epic",
            name="Epic: Godot Scene Engine",
            status="pending",
            dependencies=[epic2_id]
        )
        nodes.append(epic3_node)

        feat_build_id = f"feat_build_{uuid.uuid4().hex[:4]}"
        feat_build_node = ProjectHierarchyNode(
            node_id=feat_build_id,
            project_id=project_id,
            parent_id=epic3_id,
            node_type="feature",
            name="Feature: Construct Main Scene",
            status="pending"
        )
        nodes.append(feat_build_node)

        task_build_id = f"task_build_{uuid.uuid4().hex[:4]}"
        task_build_node = ProjectHierarchyNode(
            node_id=task_build_id,
            project_id=project_id,
            parent_id=feat_build_id,
            node_type="task",
            name="Task: Assemble Godot Scenes and assets",
            status="pending",
            dependencies=m2_tasks, # Depends on all optimization tasks completing
            metadata={"agent": "godot", "template_data": template}
        )
        self.estimate_complexity_and_duration(task_build_node)
        nodes.append(task_build_node)

        # Milestone 4: Deploy & Validation
        m4_id = f"m4_{uuid.uuid4().hex[:8]}"
        m4_node = ProjectHierarchyNode(
            node_id=m4_id,
            project_id=project_id,
            parent_id=project_node_id,
            node_type="milestone",
            name="Milestone 4: Verification and Launch",
            status="pending",
            dependencies=[m3_id]
        )
        nodes.append(m4_node)

        epic4_id = f"epic4_{uuid.uuid4().hex[:8]}"
        epic4_node = ProjectHierarchyNode(
            node_id=epic4_id,
            project_id=project_id,
            parent_id=m4_id,
            node_type="epic",
            name="Epic: Validation & Deployment",
            status="pending",
            dependencies=[epic3_id]
        )
        nodes.append(epic4_node)

        feat_val_id = f"feat_val_{uuid.uuid4().hex[:4]}"
        feat_val_node = ProjectHierarchyNode(
            node_id=feat_val_id,
            project_id=project_id,
            parent_id=epic4_id,
            node_type="feature",
            name="Feature: Deploy and Verify Quality",
            status="pending"
        )
        nodes.append(feat_val_node)

        task_val_id = f"task_val_{uuid.uuid4().hex[:4]}"
        task_val_node = ProjectHierarchyNode(
            node_id=task_val_id,
            project_id=project_id,
            parent_id=feat_val_id,
            node_type="task",
            name="Task: Quality validation and deployment check",
            status="pending",
            dependencies=[task_build_id],
            metadata={"agent": "browser", "validation_rules": template.get("ground", {})}
        )
        self.estimate_complexity_and_duration(task_val_node)
        nodes.append(task_val_node)

        # 4. Save to Database
        if self.db:
            for node in nodes:
                try:
                    self.db.add_hierarchy_node(
                        node_id=node.id,
                        project_id=node.project_id,
                        parent_id=node.parent_id,
                        node_type=node.node_type,
                        name=node.name,
                        status=node.status,
                        estimated_duration=node.estimated_duration,
                        dependencies=node.dependencies,
                        metadata=node.metadata
                    )
                except Exception as e:
                    log.warning("Database write failed for hierarchy node %s: %s", node.id, e)

        return nodes

    def estimate_complexity_and_duration(self, node: ProjectHierarchyNode) -> None:
        """Estimate complexity and duration based on historical metrics and task details."""
        meta = node.metadata
        duration = 5.0 # Base duration
        complexity = "normal"
        
        agent_type = meta.get("agent")
        if agent_type == "asset":
            terms = meta.get("search_terms", [])
            duration = max(5.0, len(terms) * 4.0)
        elif agent_type == "blender":
            duration = 10.0
        elif agent_type == "godot":
            template_data = meta.get("template_data", {})
            slots = template_data.get("asset_slots", [])
            count = sum(s.get("count", 1) for s in slots)
            duration = max(15.0, count * 2.0)
        elif agent_type == "browser":
            duration = 8.0

        # Heuristics based on name keywords
        keywords = ["multiplayer", "network", "fps", "physics", "save", "load", "audio"]
        name_lower = node.name.lower()
        match_count = sum(1 for kw in keywords if kw in name_lower)
        if match_count > 0:
            duration += match_count * 5.0
            complexity = "high" if match_count >= 2 else "medium"

        # Adjust duration based on historical success rates if brain is wired
        if self.brain and hasattr(self.brain, "memory") and self.brain.memory:
            try:
                from .worker_scorer import WorkerScoreRegistry
                score_reg = WorkerScoreRegistry(self.brain.memory)
                scores = score_reg.score_workers()
                agent_score = scores.get(agent_type or "", 0.0)
                if agent_score < 0:
                    duration *= (1.0 + abs(agent_score))
            except Exception:
                pass

        node.estimated_duration = round(duration, 2)
        node.metadata["complexity"] = complexity

    def generate_subtasks(self, project_id: str, parent_node_id: str, subtasks_list: List[str]) -> List[ProjectHierarchyNode]:
        """Generate and store subtasks dynamically in the DAG."""
        nodes: List[ProjectHierarchyNode] = []
        for i, subtask_name in enumerate(subtasks_list):
            sub_id = f"subtask_{uuid.uuid4().hex[:8]}"
            node = ProjectHierarchyNode(
                node_id=sub_id,
                project_id=project_id,
                parent_id=parent_node_id,
                node_type="subtask",
                name=subtask_name,
                status="pending"
            )
            self.estimate_complexity_and_duration(node)
            nodes.append(node)
            if self.db and hasattr(self.db, "add_hierarchy_node"):
                try:
                    self.db.add_hierarchy_node(
                        node_id=node.id,
                        project_id=node.project_id,
                        parent_id=node.parent_id,
                        node_type=node.node_type,
                        name=node.name,
                        status=node.status,
                        estimated_duration=node.estimated_duration,
                        dependencies=node.dependencies,
                        metadata=node.metadata
                    )
                except Exception as e:
                    log.warning("Failed to save subtask %s: %s", node.id, e)
        return nodes

    def get_completion_percentage(self, project_id: str) -> float:
        """Calculate project completion rate."""
        if not self.db:
            return 0.0
        try:
            nodes = self.db.get_project_hierarchy(project_id)
            if not nodes:
                return 0.0
            completed = sum(1 for n in nodes if n.get("status") == "completed")
            return round((completed / len(nodes)) * 100.0, 2)
        except Exception:
            return 0.0

    def detect_blockers(self, project_id: str) -> List[str]:
        """Detect any blocked nodes in the project DAG."""
        if not self.db:
            return []
            
        nodes = self.db.get_project_hierarchy(project_id)
        node_map = {n["id"]: n for n in nodes}
        blockers = []

        for n in nodes:
            if n["status"] in ("pending", "running"):
                for dep_id in n.get("dependencies", []):
                    dep = node_map.get(dep_id)
                    if dep and dep["status"] == "failed":
                        blockers.append(n["id"])
                        self.db.update_hierarchy_node_status(n["id"], "blocked")
                        break
        return blockers

    def dynamic_reschedule(self, project_id: str, failed_node_id: str) -> None:
        """Dynamically reschedule downstream tasks by inserting a recovery node and updating dependencies."""
        log.info("Dynamic rescheduling triggered by failure of node %s", failed_node_id)
        if not self.db:
            return

        try:
            nodes = self.db.get_project_hierarchy(project_id)
        except Exception:
            return
            
        node_map = {n["id"]: n for n in nodes}
        failed_node = node_map.get(failed_node_id)
        if not failed_node:
            return

        # 1. Create a healing recovery node
        recovery_id = f"recovery_{uuid.uuid4().hex[:8]}"
        recovery_node = ProjectHierarchyNode(
            node_id=recovery_id,
            project_id=project_id,
            parent_id=failed_node.get("parent_id"),
            node_type="task",
            name=f"Recovery Task for: {failed_node.get('name')}",
            status="pending",
            dependencies=failed_node.get("dependencies", []),
            metadata={"agent": "validation", "healing_action": "bypass_failure"}
        )
        self.estimate_complexity_and_duration(recovery_node)
        
        # Save recovery node to database
        try:
            self.db.add_hierarchy_node(
                node_id=recovery_id,
                project_id=project_id,
                parent_id=recovery_node.parent_id,
                node_type=recovery_node.node_type,
                name=recovery_node.name,
                status=recovery_node.status,
                estimated_duration=recovery_node.estimated_duration,
                dependencies=recovery_node.dependencies,
                metadata=recovery_node.metadata
            )
        except Exception as e:
            log.warning("Failed to save recovery node: %s", e)
            return

        # 2. Redirect all downstream tasks from failed_node_id to recovery_id
        for n in nodes:
            deps = n.get("dependencies", [])
            if failed_node_id in deps:
                new_deps = [d if d != failed_node_id else recovery_id for d in deps]
                try:
                    # Update dependencies in DB
                    self.db.execute(
                        "UPDATE project_hierarchy SET dependencies_json = ?, status = 'pending' WHERE id = ?",
                        (json.dumps(new_deps), n["id"])
                    )
                except Exception as e:
                    log.warning("Failed to reschedule dependency for node %s: %s", n["id"], e)

    def pause_project(self, project_id: str) -> None:
        """Pause a running project and mark its running/pending nodes as paused."""
        log.info("Pausing project: %s", project_id)
        if not self.db:
            return
        self.db.execute("UPDATE jobs SET status = 'paused' WHERE id = ?", (project_id,))
        self.db.execute(
            "UPDATE project_hierarchy SET status = 'paused' WHERE project_id = ? AND status IN ('running', 'pending')",
            (project_id,)
        )
        self.db.add_event(project_id, "Project execution paused by goal manager", stage="orchestration", level="info")

    def resume_project(self, project_id: str) -> None:
        """Resume a paused project and queue its paused nodes."""
        log.info("Resuming project: %s", project_id)
        if not self.db:
            return
        self.db.execute("UPDATE jobs SET status = 'queued' WHERE id = ?", (project_id,))
        self.db.execute(
            "UPDATE project_hierarchy SET status = 'pending' WHERE project_id = ? AND status = 'paused'",
            (project_id,)
        )
        self.db.add_event(project_id, "Project execution resumed by goal manager", stage="orchestration", level="info")

    def save_checkpoint(self, project_id: str, state_dict: Dict[str, Any]) -> None:
        """Serialize and save the current unified job/pipeline state as a checkpoint."""
        log.info("Saving checkpoint for project: %s", project_id)
        if not self.db:
            return
        try:
            # We store the checkpoint inside the world_model under key 'checkpoint_state'
            self.db.execute(
                "INSERT OR REPLACE INTO world_model (job_id, key, value_json, updated_at) VALUES (?, 'checkpoint_state', ?, ?)",
                (project_id, json.dumps(state_dict), time.time())
            )
        except Exception as e:
            log.warning("Failed to save checkpoint for %s: %s", project_id, e)

    def load_checkpoint(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve and deserialize the last checkpoint state for the project."""
        log.info("Loading checkpoint for project: %s", project_id)
        if not self.db:
            return None
        try:
            row = self.db.query_one("SELECT value_json FROM world_model WHERE job_id = ? AND key = 'checkpoint_state'", (project_id,))
            if row and row["value_json"]:
                return json.loads(row["value_json"])
        except Exception as e:
            log.warning("Failed to load checkpoint for %s: %s", project_id, e)
        return None

