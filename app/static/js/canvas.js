/**
 * ShrimpWar Canvas Editor
 * Vanilla SVG-based node editor for workflow DSL construction.
 * No framework dependencies.
 */
(function () {
    "use strict";

    // ── State ─────────────────────────────────────────────
    const state = {
        nodes: [],          // DSL node objects
        edges: [],          // DSL edge objects
        nodeEls: {},        // nodeId → SVG <g> element
        portEls: {},        // "nodeId:port" → SVG <circle>
        edgeEls: {},        // edgeId → SVG <line>
        zoom: 1,
        panX: 0,
        panY: 0,
        dragging: null,     // current drag state
        selectedNodeId: null,
        nextNodeNum: 2,     // counter for auto-generated agent node IDs
    };

    const NODE_W = 180;
    const NODE_H = 80;
    const PORT_R = 6;

    const TYPE_COLORS = {
        start: { fill: "#166534", stroke: "#22c55e", text: "#bbf7d0" },
        agent: { fill: "#1e293b", stroke: "#f97316", text: "#fed7aa" },
        end: { fill: "#1e3a5f", stroke: "#3b82f6", text: "#bfdbfe" },
    };

    // ── DOM refs ──────────────────────────────────────────
    const canvasContainer = document.getElementById("canvas-container");
    const canvasSvg = document.getElementById("canvas-svg");
    const canvasGroup = document.getElementById("canvas-group");
    const connectionsGroup = document.getElementById("connections-group");
    const nodesGroup = document.getElementById("nodes-group");
    const tempConn = document.getElementById("temp-connection");
    const flowMarker = createArrowMarker();
    canvasSvg.appendChild(flowMarker);

    // ── Initialize ────────────────────────────────────────
    function init() {
        const dsl = window.__INITIAL_DSL__;
        if (dsl && dsl.nodes && dsl.nodes.length > 0) {
            loadDSL(dsl);
        } else {
            createDefaultGraph();
        }
        renderAll();
        setupPaletteDrag();
        setupCanvasEvents();
    }

    function createDefaultGraph() {
        state.nodes = [
            { id: "chain-start", type: "start", label: "用户输入", outputKey: "user_task", position: { x: 60, y: 240 } },
            { id: "chain-end", type: "end", label: "最终输出", resultKey: "final_output", position: { x: 560, y: 240 } },
        ];
        state.edges = [];
    }

    function loadDSL(dsl) {
        state.nodes = dsl.nodes.map(n => ({ ...n }));
        state.edges = dsl.edges.map(e => ({ ...e }));

        // Ensure start and end nodes always exist
        const hasStart = state.nodes.some(n => n.type === "start");
        const hasEnd = state.nodes.some(n => n.type === "end");
        if (!hasStart) {
            state.nodes.unshift({
                id: "chain-start", type: "start", label: "用户输入",
                outputKey: "user_task", position: { x: 60, y: 240 },
            });
        }
        if (!hasEnd) {
            state.nodes.push({
                id: "chain-end", type: "end", label: "最终输出",
                resultKey: "final_output", position: { x: 560, y: 240 },
            });
        }

        // Determine next agent node number
        const agentNums = state.nodes
            .filter(n => n.type === "agent")
            .map(n => {
                const m = n.id.match(/\d+$/);
                return m ? parseInt(m[0]) : 0;
            });
        state.nextNodeNum = agentNums.length > 0 ? Math.max(...agentNums) + 1 : 2;
    }

    // ── Arrow marker ──────────────────────────────────────
    function createArrowMarker() {
        const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
        marker.setAttribute("id", "arrowhead");
        marker.setAttribute("markerWidth", "10");
        marker.setAttribute("markerHeight", "7");
        marker.setAttribute("refX", "10");
        marker.setAttribute("refY", "3.5");
        marker.setAttribute("orient", "auto");
        const arrowPath = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
        arrowPath.setAttribute("points", "0 0, 10 3.5, 0 7");
        arrowPath.setAttribute("fill", "#f97316");
        marker.appendChild(arrowPath);
        defs.appendChild(marker);
        return defs;
    }

    // ── Render ────────────────────────────────────────────
    function renderAll() {
        // Clear nodes
        nodesGroup.replaceChildren();
        state.nodeEls = {};
        state.portEls = {};

        // Clear edges
        connectionsGroup.replaceChildren();
        state.edgeEls = {};

        // Render nodes
        for (const node of state.nodes) {
            renderNode(node);
        }

        // Render edges
        for (const edge of state.edges) {
            renderEdge(edge);
        }
    }

    function renderNode(node) {
        const pos = node.position || { x: 100, y: 100 };
        const colors = TYPE_COLORS[node.type] || TYPE_COLORS.agent;

        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("id", "node-" + node.id);
        g.setAttribute("data-node-id", node.id);
        g.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);
        g.style.cursor = "pointer";

        // Click to select
        g.addEventListener("click", (e) => {
            e.stopPropagation();
            selectNode(node);
        });

        // Mouse down for dragging nodes
        g.addEventListener("mousedown", (e) => {
            if (e.target.closest("[data-port]")) return;
            e.stopPropagation();
            startNodeDrag(node.id, e.clientX, e.clientY);
        });

        // Rect
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("width", NODE_W);
        rect.setAttribute("height", NODE_H);
        rect.setAttribute("rx", "10");
        rect.setAttribute("ry", "10");
        rect.setAttribute("fill", colors.fill);
        rect.setAttribute("stroke", state.selectedNodeId === node.id ? "#eab308" : colors.stroke);
        rect.setAttribute("stroke-width", state.selectedNodeId === node.id ? "2.5" : "1.5");
        g.appendChild(rect);

        // Type badge
        const badge = document.createElementNS("http://www.w3.org/2000/svg", "text");
        badge.textContent = node.type.toUpperCase();
        badge.setAttribute("x", "10");
        badge.setAttribute("y", "18");
        badge.setAttribute("fill", colors.stroke);
        badge.setAttribute("font-size", "10");
        badge.setAttribute("font-weight", "bold");
        badge.setAttribute("font-family", "monospace");
        g.appendChild(badge);

        // Label
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.textContent = node.label || node.id;
        label.setAttribute("x", "10");
        label.setAttribute("y", "42");
        label.setAttribute("fill", colors.text);
        label.setAttribute("font-size", "13");
        label.setAttribute("font-weight", "600");
        label.setAttribute("font-family", "system-ui, sans-serif");
        g.appendChild(label);

        // Subtitle for start/end nodes
        if (node.type === "start" || node.type === "end") {
            const subtitle = document.createElementNS("http://www.w3.org/2000/svg", "text");
            subtitle.textContent = node.type === "start" ? "▼ 起点" : "▲ 终点";
            subtitle.setAttribute("x", "10");
            subtitle.setAttribute("y", "65");
            subtitle.setAttribute("fill", colors.stroke);
            subtitle.setAttribute("font-size", "11");
            subtitle.setAttribute("font-weight", "500");
            subtitle.setAttribute("font-family", "system-ui, sans-serif");
            g.appendChild(subtitle);
        }

        // Agent binding info
        if (node.type === "agent") {
            let info = "未绑定 Agent";
            if (node.agentInstanceId) {
                info = "Agent: " + node.agentInstanceId.substring(0, 8);
            }
            const agentInfo = document.createElementNS("http://www.w3.org/2000/svg", "text");
            agentInfo.textContent = info;
            agentInfo.setAttribute("x", "10");
            agentInfo.setAttribute("y", "65");
            agentInfo.setAttribute("fill", "#6b7280");
            agentInfo.setAttribute("font-size", "10");
            agentInfo.setAttribute("font-family", "system-ui, sans-serif");
            g.appendChild(agentInfo);
        }

        // Ports
        if (node.type !== "start") {
            // Input port (left)
            const inPort = createPort(0, NODE_H / 2, node.id, "input");
            g.appendChild(inPort);
            state.portEls[node.id + ":input"] = inPort;
        }
        if (node.type !== "end") {
            // Output port (right)
            const outPort = createPort(NODE_W, NODE_H / 2, node.id, "output");
            g.appendChild(outPort);
            state.portEls[node.id + ":output"] = outPort;
        }

        nodesGroup.appendChild(g);
        state.nodeEls[node.id] = g;
    }

    function createPort(x, y, nodeId, portType) {
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", x);
        circle.setAttribute("cy", y);
        circle.setAttribute("r", PORT_R);
        circle.setAttribute("fill", "#1e293b");
        circle.setAttribute("stroke", "#f97316");
        circle.setAttribute("stroke-width", "2");
        circle.setAttribute("data-port", portType);
        circle.setAttribute("data-node-id", nodeId);
        circle.style.cursor = "crosshair";

        circle.addEventListener("mousedown", (e) => {
            e.stopPropagation();
            startConnectionDrag(nodeId, portType, e.clientX, e.clientY);
        });

        return circle;
    }

    function renderEdge(edge) {
        const fromPort = getPortPosition(edge.from, "output");
        const toPort = getPortPosition(edge.to, "input");
        if (!fromPort || !toPort) return;

        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", fromPort.x);
        line.setAttribute("y1", fromPort.y);
        line.setAttribute("x2", toPort.x);
        line.setAttribute("y2", toPort.y);
        line.setAttribute("stroke", "#f97316");
        line.setAttribute("stroke-width", "2");
        line.setAttribute("marker-end", "url(#arrowhead)");
        line.setAttribute("data-edge-id", edge.id);
        connectionsGroup.appendChild(line);
        state.edgeEls[edge.id] = line;
    }

    function getPortPosition(nodeId, portType) {
        const node = state.nodes.find(n => n.id === nodeId);
        if (!node) return null;
        const pos = node.position || { x: 0, y: 0 };
        const cx = portType === "output" ? pos.x + NODE_W : pos.x;
        return { x: cx, y: pos.y + NODE_H / 2 };
    }

    // ── Efficient edge update for node drag ───────────────
    function updateEdgesForNode(nodeId) {
        for (const edge of state.edges) {
            if (edge.from !== nodeId && edge.to !== nodeId) continue;
            const line = state.edgeEls[edge.id];
            if (!line) continue;
            const fromPort = getPortPosition(edge.from, "output");
            const toPort = getPortPosition(edge.to, "input");
            if (!fromPort || !toPort) continue;
            line.setAttribute("x1", fromPort.x);
            line.setAttribute("y1", fromPort.y);
            line.setAttribute("x2", toPort.x);
            line.setAttribute("y2", toPort.y);
        }
    }

    // ── Interaction ───────────────────────────────────────
    function selectNode(node) {
        // Deselect previous node
        if (state.selectedNodeId && state.selectedNodeId !== node.id) {
            _setNodeHighlight(state.selectedNodeId, false);
        }
        // Select new node
        state.selectedNodeId = node.id;
        _setNodeHighlight(node.id, true);

        openDrawer(node);
    }

    function _setNodeHighlight(nodeId, selected) {
        const g = state.nodeEls[nodeId];
        if (!g) return;
        const rect = g.querySelector("rect");
        if (!rect) return;
        const node = state.nodes.find(n => n.id === nodeId);
        const colors = TYPE_COLORS[node?.type] || TYPE_COLORS.agent;
        rect.setAttribute("stroke", selected ? "#eab308" : colors.stroke);
        rect.setAttribute("stroke-width", selected ? "2.5" : "1.5");
    }

    function startNodeDrag(nodeId, startX, startY) {
        const node = state.nodes.find(n => n.id === nodeId);
        if (!node) return;

        state.dragging = {
            type: "node",
            nodeId: nodeId,
            origX: node.position.x,
            origY: node.position.y,
            startX: startX,
            startY: startY,
        };
    }

    function startConnectionDrag(nodeId, portType, startX, startY) {
        const portPos = getPortPosition(nodeId, portType);
        state.dragging = {
            type: "connection",
            nodeId: nodeId,
            portType: portType,
            startX: portPos.x,
            startY: portPos.y,
        };
        tempConn.setAttribute("x1", portPos.x);
        tempConn.setAttribute("y1", portPos.y);
        tempConn.setAttribute("x2", portPos.x);
        tempConn.setAttribute("y2", portPos.y);
        tempConn.style.display = "";
    }

    function setupCanvasEvents() {
        canvasContainer.addEventListener("mousemove", (e) => {
            if (!state.dragging) return;
            const svgRect = canvasSvg.getBoundingClientRect();
            const mx = (e.clientX - svgRect.left - state.panX) / state.zoom;
            const my = (e.clientY - svgRect.top - state.panY) / state.zoom;

            if (state.dragging.type === "node") {
                const dx = (e.clientX - state.dragging.startX) / state.zoom;
                const dy = (e.clientY - state.dragging.startY) / state.zoom;
                const node = state.nodes.find(n => n.id === state.dragging.nodeId);
                if (node) {
                    node.position.x = Math.max(0, state.dragging.origX + dx);
                    node.position.y = Math.max(0, state.dragging.origY + dy);
                    // Update node position directly — no full re-render
                    const g = state.nodeEls[node.id];
                    if (g) {
                        g.setAttribute("transform", `translate(${node.position.x}, ${node.position.y})`);
                    }
                    // Update connected edges
                    updateEdgesForNode(node.id);
                }
            } else if (state.dragging.type === "connection") {
                tempConn.setAttribute("x2", mx);
                tempConn.setAttribute("y2", my);
            } else if (state.dragging.type === "pan") {
                const dx = e.clientX - state.dragging.startX;
                const dy = e.clientY - state.dragging.startY;
                state.panX = state.dragging.origPanX + dx;
                state.panY = state.dragging.origPanY + dy;
                updateTransform();
            }
        });

        window.addEventListener("mouseup", (e) => {
            if (!state.dragging) return;

            if (state.dragging.type === "connection") {
                const svgRect = canvasSvg.getBoundingClientRect();
                const mx = (e.clientX - svgRect.left - state.panX) / state.zoom;
                const my = (e.clientY - svgRect.top - state.panY) / state.zoom;
                finishConnection(mx, my);
            }

            state.dragging = null;
            tempConn.style.display = "none";
        });

        // Pan on empty area
        canvasContainer.addEventListener("mousedown", (e) => {
            if (e.target === canvasSvg || e.target === canvasGroup || e.target === connectionsGroup || e.target === nodesGroup) {
                state.dragging = {
                    type: "pan",
                    startX: e.clientX,
                    startY: e.clientY,
                    origPanX: state.panX,
                    origPanY: state.panY,
                };
                canvasSvg.style.cursor = "grabbing";
            }
        });

        window.addEventListener("mouseup", () => {
            if (state.dragging && state.dragging.type === "pan") {
                canvasSvg.style.cursor = "grab";
            }
            state.dragging = null;
            tempConn.style.display = "none";
        });
    }

    function finishConnection(mx, my) {
        // Find which node/port the mouse is over
        for (const node of state.nodes) {
            if (node.id === state.dragging.nodeId) continue;
            const pos = node.position;
            if (!pos) continue;

            if (mx >= pos.x - 10 && mx <= pos.x + NODE_W + 10 &&
                my >= pos.y - 10 && my <= pos.y + NODE_H + 10) {

                const sourceId = state.dragging.nodeId;
                const sourcePort = state.dragging.portType;

                let fromId, toId;
                if (sourcePort === "output") {
                    fromId = sourceId;
                    toId = node.id;
                } else {
                    fromId = node.id;
                    toId = sourceId;
                }

                // Validate: from must have output port, to must have input port
                const fromNode = state.nodes.find(n => n.id === fromId);
                const toNode = state.nodes.find(n => n.id === toId);
                if (!fromNode || !toNode) return;
                if (fromNode.type === "end") return;
                if (toNode.type === "start") return;

                // Remove existing connection between these two
                state.edges = state.edges.filter(
                    e => !(e.from === fromId && e.to === toId)
                );

                // Add new connection
                const edgeId = "e" + Date.now();
                state.edges.push({ id: edgeId, from: fromId, to: toId });
                renderAll();
                return;
            }
        }
    }

    function updateTransform() {
        canvasGroup.setAttribute(
            "transform",
            `translate(${state.panX}, ${state.panY}) scale(${state.zoom})`
        );
    }

    // ── Palette drag ──────────────────────────────────────
    function setupPaletteDrag() {
        const paletteNodes = document.querySelectorAll(".palette-node");
        paletteNodes.forEach(el => {
            el.addEventListener("dragstart", (e) => {
                e.dataTransfer.setData("text/plain", e.target.dataset.nodeType);
                e.dataTransfer.effectAllowed = "copy";
            });
        });

        canvasContainer.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
        });

        canvasContainer.addEventListener("drop", (e) => {
            e.preventDefault();
            const nodeType = e.dataTransfer.getData("text/plain");
            if (nodeType !== "agent") return;

            const svgRect = canvasSvg.getBoundingClientRect();
            const x = (e.clientX - svgRect.left - state.panX) / state.zoom - NODE_W / 2;
            const y = (e.clientY - svgRect.top - state.panY) / state.zoom - NODE_H / 2;

            const nodeId = "chain-agent-" + state.nextNodeNum;
            state.nextNodeNum += 1;

            state.nodes.push({
                id: nodeId,
                type: "agent",
                label: "Agent 节点",
                role: "",
                kind: "worker",
                agentInstanceId: null,
                inputTemplate: "协作身份：执行者\n期望输入：用户任务\n期望输出：处理结果\n\n{{upstream_outputs}}",
                outputKey: nodeId + "_output",
                isManager: false,
                position: { x: Math.max(0, Math.round(x)), y: Math.max(0, Math.round(y)) },
            });

            renderAll();
        });
    }

    // ── Drawer ────────────────────────────────────────────
    function openDrawer(node) {
        document.getElementById("cfg-node-id").value = node.id;
        document.getElementById("cfg-label").value = node.label || "";

        const isAgent = node.type === "agent";
        // Toggle field groups based on node type
        const agentFields = document.querySelectorAll(".cfg-agent-only");
        const startEndFields = document.querySelectorAll(".cfg-startend-only");
        const deleteBtn = document.getElementById("cfg-delete-btn");

        agentFields.forEach(el => el.style.display = isAgent ? "" : "none");
        startEndFields.forEach(el => el.style.display = isAgent ? "none" : "");
        if (deleteBtn) deleteBtn.style.display = isAgent ? "" : "none";

        if (isAgent) {
            document.getElementById("cfg-role").value = node.role || "";
            document.getElementById("cfg-kind").value = node.kind || "worker";
            document.getElementById("cfg-agent").value = node.agentInstanceId || "";
            document.getElementById("cfg-template").value = node.inputTemplate || "";
        } else {
            // Show type-specific info for start/end
            const typeLabel = node.type === "start" ? "起点 (用户输入)" : "终点 (最终输出)";
            document.getElementById("cfg-type-display").textContent = typeLabel;
            document.getElementById("cfg-key-display").textContent =
                node.type === "start" ? (node.outputKey || "") : (node.resultKey || "");
        }

        document.getElementById("config-overlay").classList.remove("hidden");
        document.getElementById("config-drawer").classList.remove("translate-x-full");
    }

    function closeDrawer() {
        document.getElementById("config-overlay").classList.add("hidden");
        document.getElementById("config-drawer").classList.add("translate-x-full");
        state.selectedNodeId = null;
        // Deselect highlight
        for (const nodeId of Object.keys(state.nodeEls)) {
            _setNodeHighlight(nodeId, false);
        }
    }

    function saveNodeConfig() {
        const nodeId = document.getElementById("cfg-node-id").value;
        const node = state.nodes.find(n => n.id === nodeId);
        if (!node) return;

        node.label = document.getElementById("cfg-label").value;

        if (node.type === "agent") {
            node.role = document.getElementById("cfg-role").value;
            node.kind = document.getElementById("cfg-kind").value;
            node.agentInstanceId = document.getElementById("cfg-agent").value || null;
            node.inputTemplate = document.getElementById("cfg-template").value;
            node.isManager = node.kind === "orchestrator";
        }

        closeDrawer();
        renderAll();
    }

    function deleteNode() {
        const nodeId = document.getElementById("cfg-node-id").value;
        const node = state.nodes.find(n => n.id === nodeId);
        if (!node || node.type === "start" || node.type === "end") return;

        state.nodes = state.nodes.filter(n => n.id !== nodeId);
        state.edges = state.edges.filter(e => e.from !== nodeId && e.to !== nodeId);
        closeDrawer();
        renderAll();
    }

    // ── Zoom ──────────────────────────────────────────────
    function zoomIn() {
        state.zoom = Math.min(2, state.zoom + 0.1);
        updateTransform();
    }

    function zoomOut() {
        state.zoom = Math.max(0.3, state.zoom - 0.1);
        updateTransform();
    }

    function resetZoom() {
        state.zoom = 1;
        state.panX = 0;
        state.panY = 0;
        updateTransform();
    }

    // ── Save / Run ────────────────────────────────────────
    async function saveTeam() {
        const name = document.getElementById("team-name").value.trim() || "未命名团队";
        const desc = document.getElementById("team-desc").value.trim();

        const dsl = {
            schemaVersion: "1.0",
            name: name,
            description: desc,
            entryNodeId: state.nodes.find(n => n.type === "start")?.id || "",
            nodes: state.nodes,
            edges: state.edges,
            execution: {
                mode: "chain",
                maxConcurrency: 1,
                timeoutSec: 1800,
            },
            metadata: {
                source: "canvas",
                collaborationPattern: "prompt-chain",
                warnings: [],
            },
        };

        const teamId = window.__TEAM_ID__;

        try {
            if (teamId) {
                const resp = await fetch(`/api/teams/${teamId}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, description: desc, dsl: JSON.stringify(dsl) }),
                });
                if (resp.ok) {
                    showToast("保存成功");
                } else {
                    showToast("保存失败", true);
                }
            } else {
                const resp = await fetch("/api/teams", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, description: desc }),
                });
                if (resp.ok) {
                    const team = await resp.json();
                    // Then update with DSL
                    await fetch(`/api/teams/${team.id}`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ name, description: desc, dsl: JSON.stringify(dsl) }),
                    });
                    window.__TEAM_ID__ = team.id;
                    history.replaceState(null, "", `/teams/${team.id}`);
                    showToast("创建成功");
                } else {
                    showToast("创建失败", true);
                }
            }
        } catch (err) {
            showToast("保存失败: " + err.message, true);
        }
    }

    function goRun() {
        if (!window.__TEAM_ID__) {
            showToast("请先保存团队", true);
            return;
        }
        window.location.href = `/teams/${window.__TEAM_ID__}/run`;
    }

    function showToast(msg, isError) {
        const existing = document.querySelector(".canvas-toast");
        if (existing) existing.remove();

        const toast = document.createElement("div");
        toast.className = "canvas-toast fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-sm z-50 transition-opacity duration-300 " +
            (isError ? "bg-red-500/20 text-red-300" : "bg-green-500/20 text-green-300");
        toast.textContent = msg;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 300);
        }, 2000);
    }

    // ── Exports ───────────────────────────────────────────
    window.saveTeam = saveTeam;
    window.goRun = goRun;
    window.closeDrawer = closeDrawer;
    window.saveNodeConfig = saveNodeConfig;
    window.deleteNode = deleteNode;
    window.zoomIn = zoomIn;
    window.zoomOut = zoomOut;
    window.resetZoom = resetZoom;

    // ── Start ─────────────────────────────────────────────
    init();
})();
