"""Native zero-dependency implementation of a LangGraph StateGraph for reasoning."""
from __future__ import annotations
from typing import Any, Callable, Dict, Optional, Union

class StateGraph:
    """A native StateGraph implementation mimicking LangGraph."""
    def __init__(self):
        self.nodes: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, tuple[Callable[[Dict[str, Any]], str], Dict[str, str]]] = {}
        self.entry_point: Optional[str] = None
        self.finish_point: str = "__end__"

    def add_node(self, name: str, action: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.nodes[name] = action

    def add_edge(self, from_node: str, to_node: str) -> None:
        self.edges[from_node] = to_node

    def add_conditional_edges(
        self,
        from_node: str,
        condition: Callable[[Dict[str, Any]], str],
        path_map: Dict[str, str]
    ) -> None:
        self.conditional_edges[from_node] = (condition, path_map)

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def compile(self) -> CompiledStateGraph:
        if not self.entry_point:
            raise ValueError("Entry point must be set before compiling StateGraph.")
        return CompiledStateGraph(self)


class CompiledStateGraph:
    """Compiled runnable execution engine for the StateGraph."""
    def __init__(self, graph: StateGraph):
        self.graph = graph

    def invoke(self, initial_state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = dict(initial_state)
        current = self.graph.entry_point

        # Track execution path for debugging & override tools
        state["_graph_path"] = state.get("_graph_path", [])
        state["_graph_path"].append(current)

        visited = set()
        loop_counter = 0

        while current and current != "__end__":
            # Prevent infinite loops in malformed graphs
            state_key = f"{current}_{loop_counter}"
            if state_key in visited:
                break
            visited.add(state_key)
            loop_counter += 1
            if loop_counter > 50:
                break

            # Execute node
            node_action = self.graph.nodes.get(current)
            if node_action:
                # Execute node with safety wrapper
                try:
                    state = node_action(state)
                except Exception as e:
                    state["_error"] = str(e)
                    state["_failed_node"] = current
                    # Fallback to replanning or break
                    if "replan" in self.graph.nodes and current != "replan":
                        current = "replan"
                        state["_graph_path"].append(current)
                        continue
                    else:
                        break

            # Route to next node
            next_node = None
            if current in self.graph.conditional_edges:
                cond_fn, path_map = self.graph.conditional_edges[current]
                decision = cond_fn(state)
                next_node = path_map.get(decision, "__end__")
            elif current in self.graph.edges:
                next_node = self.graph.edges[current]
            else:
                next_node = "__end__"

            current = next_node
            if current:
                state["_graph_path"].append(current)

        return state
