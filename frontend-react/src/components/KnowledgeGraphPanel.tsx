import { Alert, Badge, Button, Card, Col, Descriptions, Row, Select, Space, Table, Tabs, Tag, Tooltip, Typography } from "antd";
import { useMemo, useState } from "react";
import type { KnowledgeGraphLink, KnowledgeGraphNode } from "../types/graph";
import { GraphView, type GraphLayoutType } from "./GraphView";

// 社区颜色调色板（比基础调色板更丰富）
const COMMUNITY_PALETTE = [
  "#4285F4",  // 谷歌蓝
  "#EA4335",  // 谷歌红
  "#FBBC05",  // 谷歌黄
  "#34A853",  // 谷歌绿
  "#7B1FA2",  // 紫色
  "#0097A7",  // 青色
  "#FF6D00",  // 橙色
  "#757575",  // 灰色
  "#607D8B",  // 蓝灰色
  "#C2185B",  // 粉色
  "#3F51B5",  // 靛蓝
  "#009688",  // 蓝绿
  "#8BC34A",  // 浅绿
  "#FF9800",  // 深橙
  "#795548",  // 棕色
  "#9E9E9E",  // 中灰
  "#673AB7",  // 深紫
  "#E91E63",  // 粉红
  "#FFC107",  // 琥珀
  "#00BCD4",  // 青色
];

function toNodeRows(nodes: KnowledgeGraphNode[]) {
  return nodes.map((n, idx) => ({
    key: String(n.id ?? idx),
    id: n.id,
    label: n.label,
    group: n.group,
    description: n.description,
    raw: n,
  }));
}

function toLinkRows(links: KnowledgeGraphLink[]) {
  return links.map((l, idx) => ({
    key: `${String(l.source ?? "")}-${String(l.label ?? "")}-${String(l.target ?? "")}-${idx}`,
    source: l.source,
    target: l.target,
    label: l.label,
    weight: l.weight,
    raw: l,
  }));
}

// 计算社区统计信息
function computeCommunityStats(nodes: KnowledgeGraphNode[]) {
  const stats = new Map<string, { count: number; sampleIds: string[] }>();

  for (const n of nodes) {
    const g = typeof n.group === "string" && n.group.trim() ? n.group.trim() : "Unknown";
    const existing = stats.get(g) || { count: 0, sampleIds: [] };
    existing.count++;
    if (existing.sampleIds.length < 3) {
      existing.sampleIds.push(String(n.id ?? ""));
    }
    stats.set(g, existing);
  }

  return Array.from(stats.entries())
    .map(([group, { count, sampleIds }]) => ({ group, count, sampleIds }))
    .sort((a, b) => b.count - a.count);
}

// 获取社区颜色
function getCommunityColor(group: string, index: number): string {
  return COMMUNITY_PALETTE[index % COMMUNITY_PALETTE.length];
}

export function KnowledgeGraphPanel(props: {
  nodes: KnowledgeGraphNode[];
  links: KnowledgeGraphLink[];
  raw?: unknown;
  error?: string | null;
  height?: number;
}) {
  const { nodes, links, raw, error, height = 520 } = props;
  const [layoutType, setLayoutType] = useState<GraphLayoutType>("force");
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [showLegend, setShowLegend] = useState<boolean>(true);

  // 计算社区统计
  const communityStats = useMemo(() => computeCommunityStats(nodes), [nodes]);

  // 为每个社区分配颜色
  const communityColorMap = useMemo(() => {
    const map = new Map<string, string>();
    communityStats.forEach((stat, idx) => {
      map.set(stat.group, getCommunityColor(stat.group, idx));
    });
    return map;
  }, [communityStats]);

  const groupOptions = useMemo(() => {
    const set = new Set<string>();
    for (const n of nodes) {
      const g = typeof n.group === "string" && n.group.trim() ? n.group.trim() : "Unknown";
      set.add(g);
    }
    return Array.from(set)
      .sort()
      .map((g) => ({ label: g, value: g }));
  }, [nodes]);

  const { filteredNodes, filteredLinks } = useMemo(() => {
    if (!selectedGroups.length) return { filteredNodes: nodes, filteredLinks: links };
    const allowed = new Set(selectedGroups);
    const keptNodes = nodes.filter((n) => {
      const g = typeof n.group === "string" && n.group.trim() ? n.group.trim() : "Unknown";
      return allowed.has(g);
    });
    const nodeIds = new Set(keptNodes.map((n) => String(n.id ?? "")));
    const keptLinks = links.filter((l) => nodeIds.has(String(l.source)) && nodeIds.has(String(l.target)));
    return { filteredNodes: keptNodes, filteredLinks: keptLinks };
  }, [links, nodes, selectedGroups]);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      {error ? <Alert type="error" message={error} /> : null}
      <Alert
        type="info"
        showIcon
        message={
          <Space>
            <span>nodes={nodes.length} links={links.length}</span>
            <span>communities={communityStats.length}</span>
          </Space>
        }
      />

      <Space wrap>
        <Typography.Text type="secondary">layout</Typography.Text>
        <Select
          value={layoutType}
          style={{ width: 160 }}
          options={[
            { label: "force", value: "force" },
            { label: "circular", value: "circular" },
            { label: "radial", value: "radial" },
          ]}
          onChange={(v) => setLayoutType(v)}
        />
        <Typography.Text type="secondary">group 过滤</Typography.Text>
        <Select
          mode="multiple"
          allowClear
          maxTagCount={3}
          placeholder="不选=全部"
          style={{ minWidth: 320 }}
          value={selectedGroups}
          options={groupOptions}
          onChange={(v) => setSelectedGroups(v)}
        />
        <Button onClick={() => setSelectedGroups([])} disabled={!selectedGroups.length}>
          重置过滤
        </Button>
        <Button onClick={() => setShowLegend(!showLegend)}>
          {showLegend ? "隐藏" : "显示"}社区图例
        </Button>
      </Space>

      {/* 社区统计和颜色图例 */}
      {showLegend && communityStats.length > 0 && (
        <Card
          size="small"
          title={<Typography.Text strong>社区分布 (按节点数排序)</Typography.Text>}
          style={{ backgroundColor: "#fafafa" }}
        >
          <div
            style={{
              maxHeight: "400px",
              overflowY: "auto",
              paddingRight: "8px",
            }}
          >
            <Row gutter={[16, 16]}>
              {communityStats.map((stat) => {
                const color = communityColorMap.get(stat.group) || "#999";
                return (
                  <Col key={stat.group} xs={24} sm={12} md={8} lg={6} xl={4}>
                    <Tooltip
                      title={
                        <div>
                          <div>社区: {stat.group}</div>
                          <div>节点数: {stat.count}</div>
                          <div>示例: {stat.sampleIds.slice(0, 2).join(", ")}</div>
                        </div>
                      }
                    >
                      <div
                        style={{
                          padding: "12px 14px",
                          background: "white",
                          borderRadius: 8,
                          border: `2px solid ${color}`,
                          cursor: "pointer",
                          transition: "all 0.2s",
                          minHeight: "90px",
                          display: "flex",
                          flexDirection: "column",
                          justifyContent: "center",
                        }}
                        onClick={() => {
                          setSelectedGroups([stat.group]);
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = "scale(1.02)";
                          e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = "scale(1)";
                          e.currentTarget.style.boxShadow = "none";
                        }}
                      >
                        <Space direction="vertical" size={6} style={{ width: "100%" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <Tag color={color} style={{ margin: 0, fontWeight: "bold", fontSize: "13px" }}>
                              {stat.group}
                            </Tag>
                            <Badge
                              count={stat.count}
                              style={{
                                backgroundColor: color,
                                fontSize: "12px"
                              }}
                              overflowCount={999}
                            />
                          </div>
                          {selectedGroups.includes(stat.group) && (
                            <Tag color="success" style={{ margin: 0 }}>
                              已过滤
                            </Tag>
                          )}
                          <div style={{ fontSize: "11px", color: "#666", marginTop: "2px" }}>
                            示例: {stat.sampleIds.slice(0, 2).join(", ")}
                            {stat.sampleIds.length > 2 && "..."}
                          </div>
                        </Space>
                      </div>
                    </Tooltip>
                  </Col>
                );
              })}
            </Row>
          </div>
        </Card>
      )}

      <Tabs
        items={[
          {
            key: "viz",
            label: `可视化 (${filteredNodes.length})`,
            children: (
              <GraphView
                nodes={filteredNodes as unknown as Array<Record<string, unknown>>}
                links={filteredLinks as unknown as Array<Record<string, unknown>>}
                height={height}
                layoutType={layoutType}
              />
            ),
          },
          {
            key: "nodes",
            label: `节点 (${filteredNodes.length})`,
            children: (
              <Table
                size="small"
                rowKey="key"
                dataSource={toNodeRows(filteredNodes)}
                pagination={{ pageSize: 10 }}
                columns={[
                  { title: "id", dataIndex: "id", width: 260, ellipsis: true },
                  { title: "group", dataIndex: "group", width: 160, ellipsis: true },
                  { title: "description", dataIndex: "description", ellipsis: true },
                ]}
              />
            ),
          },
          {
            key: "links",
            label: `边 (${filteredLinks.length})`,
            children: (
              <Table
                size="small"
                rowKey="key"
                dataSource={toLinkRows(filteredLinks)}
                pagination={{ pageSize: 10 }}
                columns={[
                  { title: "source", dataIndex: "source", width: 240, ellipsis: true },
                  { title: "label", dataIndex: "label", width: 180, ellipsis: true },
                  { title: "target", dataIndex: "target", width: 240, ellipsis: true },
                  { title: "weight", dataIndex: "weight", width: 120 },
                ]}
              />
            ),
          },
          {
            key: "raw",
            label: "原始数据",
            children: (
              <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                {raw ? JSON.stringify(raw, null, 2) : "暂无数据"}
              </pre>
            ),
          },
        ]}
      />
    </Space>
  );
}

