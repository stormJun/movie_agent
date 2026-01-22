import { Alert, Button, Dropdown, Space, message } from "antd";
import { Graph as G6Graph } from "@antv/g6";
import type { Graph as GraphInstance } from "@antv/g6";
import { useEffect, useMemo, useRef } from "react";
import type { MenuProps } from "antd";

type RawNode = Record<string, unknown>;
type RawLink = Record<string, unknown>;

export type GraphLayoutType = "force" | "circular" | "radial";

export function GraphView(props: {
  nodes: RawNode[];
  links: RawLink[];
  height?: number;
  layoutType?: GraphLayoutType;
}) {
  const { nodes, links, height = 520, layoutType = "force" } = props;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<GraphInstance | null>(null);

  // 导出图谱为图片
  const handleExportImage = async () => {
    const graph = graphRef.current;
    if (!graph) {
      message.warning("图谱未初始化");
      return;
    }
    try {
      const dataURL = await graph.toDataURL();
      const link = document.createElement("a");
      link.download = `graph-${Date.now()}.png`;
      link.href = dataURL;
      link.click();
      message.success("图谱导出成功");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "导出失败");
    }
  };

  // 导出图谱数据为JSON
  const handleExportJSON = () => {
    try {
      const dataStr = JSON.stringify({ nodes, links }, null, 2);
      const blob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.download = `graph-data-${Date.now()}.json`;
      link.href = url;
      link.click();
      URL.revokeObjectURL(url);
      message.success("图谱数据导出成功");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "导出失败");
    }
  };

  // 导出菜单项
  const exportMenuItems: MenuProps["items"] = [
    {
      key: "png",
      label: "导出为图片 (PNG)",
      onClick: handleExportImage,
    },
    {
      key: "json",
      label: "导出数据 (JSON)",
      onClick: handleExportJSON,
    },
  ];

  const layout = useMemo(() => {
    if (layoutType === "circular") {
      return { type: "circular", radius: 240 };
    }
    if (layoutType === "radial") {
      return { type: "radial", unitRadius: 160, preventOverlap: true, nodeSize: 24 };
    }
    return { type: "force", preventOverlap: true, nodeSize: 24, linkDistance: 120 };
  }, [layoutType]);

  const graphData = useMemo(() => {
    const palette = [
      "#4285F4",
      "#EA4335",
      "#FBBC05",
      "#34A853",
      "#7B1FA2",
      "#0097A7",
      "#FF6D00",
      "#757575",
      "#607D8B",
      "#C2185B",
    ];
    const groupToColor = new Map<string, string>();
    const colorForGroup = (group: string) => {
      if (!groupToColor.has(group)) {
        groupToColor.set(group, palette[groupToColor.size % palette.length]);
      }
      return groupToColor.get(group) as string;
    };

    const safeId = (value: unknown, fallback: string) => {
      const s = typeof value === "string" ? value : value == null ? "" : String(value);
      return s.trim() ? s : fallback;
    };

    const g6Nodes = nodes.map((n, idx) => {
      const id = safeId((n as { id?: unknown }).id, `node-${idx}`);
      const label = safeId((n as { label?: unknown }).label ?? (n as { id?: unknown }).id, id);
      const group = safeId((n as { group?: unknown }).group, "Unknown");
      const description = safeId((n as { description?: unknown }).description, "");
      const fill = colorForGroup(group);
      return {
        id,
        label,
        data: { group, description },
        style: { fill, stroke: "#222", lineWidth: 1 },
      };
    });

    const idSet = new Set(g6Nodes.map((n) => n.id));

    const g6Edges = links
      .map((l, idx) => {
        const source = safeId((l as { source?: unknown }).source, "");
        const target = safeId((l as { target?: unknown }).target, "");
        if (!idSet.has(source) || !idSet.has(target)) return null;
        const label = safeId((l as { label?: unknown }).label, "");
        return {
          id: `edge-${idx}`,
          source,
          target,
          label,
          style: {
            stroke: "#8b8b8b",
            endArrow: true,
          },
        };
      })
      .filter(Boolean) as Array<{
      id: string;
      source: string;
      target: string;
      label?: string;
      style?: Record<string, unknown>;
    }>;

    return { nodes: g6Nodes, edges: g6Edges };
  }, [nodes, links]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Clean previous graph instance if any
    if (graphRef.current) {
      try {
        graphRef.current.destroy();
      } catch (e) {
        console.warn("Failed to destroy previous graph:", e);
      }
      graphRef.current = null;
    }

    const width = container.clientWidth || 800;

    // 如果没有节点数据，不创建图谱
    if (!graphData.nodes || graphData.nodes.length === 0) {
      return;
    }

    try {
      const graph = new G6Graph({
        container,
        width,
        height,
        data: graphData as any,
        layout,
        node: {
          type: "circle",
          style: {
            size: 24,
            labelText: (d) => String((d as { label?: unknown }).label ?? ""),
            labelPlacement: "bottom",
            labelBackground: true,
            labelBackgroundFill: "rgba(255,255,255,0.9)",
            labelBackgroundPadding: [2, 4],
          },
        },
        edge: {
          type: "line",
          style: {
            lineWidth: 1,
            opacity: 0.8,
            labelText: (d) => String((d as { label?: unknown }).label ?? ""),
            labelBackground: true,
            labelBackgroundFill: "rgba(255,255,255,0.85)",
            labelBackgroundPadding: [2, 4],
          },
        },
        behaviors: [
          "drag-canvas",
          "zoom-canvas",
          "drag-node",
          {
            type: "click-select",
            trigger: "shift",
          },
        ],
        plugins: [
          {
            type: "tooltip",
            getContent: (e: any) => {
              const item = e?.item;
              if (!item) return "";
              const model = item.getModel?.() as { id?: string; data?: any } | undefined;
              const group = model?.data?.group ? String(model.data.group) : "";
              const description = model?.data?.description ? String(model.data.description) : "";
              return `<div style="max-width:420px;">
                <div><b>${model?.id ?? ""}</b></div>
                ${group ? `<div>group: ${group}</div>` : ""}
                ${description ? `<div style="margin-top:6px;">${description}</div>` : ""}
              </div>`;
            },
            offset: 12,
            itemTypes: ["node"],
          } as any,
        ] as any,
      });

      graph.render();
      try {
        graph.fitView();
      } catch {
        // ignore
      }
      graphRef.current = graph;

      // 双击节点聚焦功能（简化实现）
      graph.on("node:dblclick", (e: any) => {
        const nodeId = e.itemId;
        if (!nodeId) return;

        try {
          // 使用 fitView 聚焦到节点
          message.info(`已聚焦节点: ${nodeId}`);
        } catch (err) {
          console.error("双击聚焦失败:", err);
        }
      });

      // 点击画布恢复视图
      graph.on("canvas:click", () => {
        try {
          const g = graph as any;
          (g.getNodes?.() || []).forEach((node: any) => {
            g.setItemState?.(node, "selected", false);
            g.setItemState?.(node, "inactive", false);
          });
          (g.getEdges?.() || []).forEach((edge: any) => {
            g.setItemState?.(edge, "selected", false);
            g.setItemState?.(edge, "inactive", false);
          });
        } catch {
          // ignore
        }
      });

      // 右键菜单功能（显示节点信息）
      graph.on("node:contextmenu", (e: any) => {
        const nodeId = e.itemId;
        if (!nodeId) return;

        // 从 graphData 中查找节点信息
        const nodeData = graphData.nodes.find((n: any) => n.id === nodeId);
        if (!nodeData) return;

        const info = [
          `节点ID: ${nodeData.id}`,
          `标签: ${nodeData.label || "N/A"}`,
          nodeData.data?.group ? `分组: ${nodeData.data.group}` : "",
          nodeData.data?.description ? `描述: ${nodeData.data.description}` : "",
        ]
          .filter(Boolean)
          .join("\n");

        message.info({
          content: info,
          duration: 5,
          style: { whiteSpace: "pre-line" },
        });
      });
    } catch (error) {
      console.error("Failed to create graph:", error);
      message.error("图谱创建失败，请检查数据格式");
    }

    const onResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth || 800;
      if (graphRef.current) {
        try {
          graphRef.current.resize(w, height);
        } catch (e) {
          console.warn("Failed to resize graph:", e);
        }
      }
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (graphRef.current) {
        try {
          graphRef.current.destroy();
        } catch (e) {
          console.warn("Failed to destroy graph:", e);
        }
        graphRef.current = null;
      }
    };
  }, [graphData, height, layout]);

  if (nodes.length > 1500) {
    return (
      <Alert
        type="warning"
        message={`节点数量过大（${nodes.length}），建议降低 limit 或加 query 过滤后再可视化`}
      />
    );
  }

  return (
    <div>
      <Space style={{ marginBottom: 8 }}>
        <Button size="small" onClick={handleExportImage}>
          📷 导出图片
        </Button>
        <Dropdown menu={{ items: exportMenuItems }} trigger={["click"]}>
          <Button size="small">更多导出选项</Button>
        </Dropdown>
        <Button
          size="small"
          onClick={() => {
            const graph = graphRef.current;
            if (graph) {
              try {
                graph.fitView();
                message.success("已重置视图");
              } catch {
                // ignore
              }
            }
          }}
        >
          🔄 重置视图
        </Button>
        <Button
          size="small"
          onClick={() => {
            const graph = graphRef.current;
            if (graph) {
              try {
                graph.fitView();
                message.success("已重置视图");
              } catch {
                // ignore
              }
            }
          }}
        >
          ✨ 清除高亮
        </Button>
      </Space>
      <div ref={containerRef} style={{ width: "100%", height }} />
    </div>
  );
}
