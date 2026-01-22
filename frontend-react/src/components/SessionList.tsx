import { useEffect, useState } from "react";
import { Button, List, Typography, Space, theme } from "antd";
import { PlusOutlined, MessageOutlined } from "@ant-design/icons";
import { listConversations, type ConversationItem } from "../services/chat";

interface SessionListProps {
    userId: string;
    currentSessionId: string;
    onSelectSession: (sessionId: string) => void;
    onNewSession: () => void;
    className?: string;
    style?: React.CSSProperties;
}

export function SessionList({
    userId,
    currentSessionId,
    onSelectSession,
    onNewSession,
    className,
    style,
}: SessionListProps) {
    const [sessions, setSessions] = useState<ConversationItem[]>([]);
    const [loading, setLoading] = useState(false);
    const { token } = theme.useToken();

    const fetchSessions = async () => {
        if (!userId) return;
        setLoading(true);
        try {
            const data = await listConversations(userId);
            setSessions(data);
        } catch (e) {
            console.error("Failed to fetch sessions", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, [userId]);

    // Expose a way to refresh list? 
    // For now simple polling or dependency on currentSessionId might be enough if we want to auto-refresh 
    // when a new session is actually created/interacted with. 
    // Let's trigger refresh when currentSessionId changes, purely to ensure list is up to date 
    // if we just created a new one and sent a message.
    useEffect(() => {
        fetchSessions();
    }, [currentSessionId]);

    return (
        <div
            className={className}
            style={{
                width: 260,
                borderRight: `1px solid ${token.colorBorderSecondary}`,
                display: "flex",
                flexDirection: "column",
                backgroundColor: token.colorBgContainer,
                ...style,
            }}
        >
            <div style={{ padding: 16 }}>
                <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={onNewSession}
                    block
                    style={{ marginBottom: 12 }}
                >
                    新会话
                </Button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "0 8px" }}>
                <List
                    loading={loading}
                    dataSource={sessions}
                    renderItem={(item) => {
                        const isSelected = item.session_id === currentSessionId;
                        return (
                            <List.Item
                                onClick={() => onSelectSession(item.session_id)}
                                style={{
                                    cursor: "pointer",
                                    padding: "10px 12px",
                                    borderRadius: token.borderRadius,
                                    backgroundColor: isSelected ? token.colorPrimaryBg : "transparent",
                                    color: isSelected ? token.colorText : token.colorTextSecondary,
                                    transition: "all 0.2s",
                                    borderBlockEnd: "none",
                                    marginBottom: 4,
                                }}
                                className={isSelected ? "session-item-selected" : "session-item"}
                            >
                                <div style={{ width: "100%", overflow: "hidden" }}>
                                    <div
                                        style={{
                                            display: "flex",
                                            justifyContent: "space-between",
                                            marginBottom: 4,
                                        }}
                                    >
                                        <Typography.Text
                                            strong={isSelected}
                                            ellipsis
                                            style={{ fontSize: 13, color: isSelected ? token.colorText : token.colorText }}
                                        >
                                            {new Date(item.updated_at).toLocaleDateString()}
                                        </Typography.Text>
                                        <Typography.Text type="secondary" style={{ fontSize: 10 }}>
                                            {new Date(item.updated_at).toLocaleTimeString([], {
                                                hour: "2-digit",
                                                minute: "2-digit",
                                            })}
                                        </Typography.Text>
                                    </div>
                                    <div style={{ display: "flex", alignItems: "flex-start" }}>
                                        <MessageOutlined
                                            style={{
                                                marginRight: 8,
                                                marginTop: 4,
                                                fontSize: 12,
                                                opacity: 0.6,
                                            }}
                                        />
                                        <Typography.Text
                                            ellipsis
                                            type={isSelected ? undefined : "secondary"}
                                            style={{ fontSize: 12, flex: 1 }}
                                        >
                                            {item.first_message || "新会话"}
                                        </Typography.Text>
                                    </div>
                                </div>
                            </List.Item>
                        );
                    }}
                />
            </div>
        </div>
    );
}
