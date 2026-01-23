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
    mode = "vertical", // 'vertical' | 'horizontal'
}: SessionListProps & { mode?: "vertical" | "horizontal" }) {
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

    useEffect(() => {
        fetchSessions();
    }, [currentSessionId]);

    const isHorizontal = mode === "horizontal";

    return (
        <div
            className={`session-list-container ${isHorizontal ? "horizontal" : ""} ${className || ""}`}
            style={style}
        >
            <div className="session-list-header">
                <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={onNewSession}
                    className="new-session-button"
                    shape={isHorizontal ? "circle" : "default"}
                >
                    {isHorizontal ? null : "新会话"}
                </Button>
            </div>
            <div className="session-list-content">
                <List
                    loading={loading}
                    dataSource={sessions}
                    grid={isHorizontal ? { gutter: 16, column: sessions.length } : undefined}
                    className={isHorizontal ? "horizontal-list" : ""}
                    renderItem={(item) => {
                        const isSelected = item.session_id === currentSessionId;
                        return (
                            <List.Item
                                onClick={() => onSelectSession(item.session_id)}
                                className={`session-item ${isSelected ? "active" : ""}`}
                                style={isHorizontal ? { marginBottom: 0 } : undefined}
                            >
                                <div className="session-item-content">
                                    <div className="session-item-header">
                                        <Typography.Text
                                            strong={isSelected}
                                            ellipsis
                                            className="session-date"
                                        >
                                            {new Date(item.updated_at).toLocaleDateString()}
                                        </Typography.Text>
                                        {!isHorizontal && (
                                            <Typography.Text type="secondary" className="session-time">
                                                {new Date(item.updated_at).toLocaleTimeString([], {
                                                    hour: "2-digit",
                                                    minute: "2-digit",
                                                })}
                                            </Typography.Text>
                                        )}
                                    </div>
                                    <div className="session-item-body">
                                        <MessageOutlined className="session-icon" />
                                        <Typography.Text
                                            ellipsis
                                            type={isSelected ? undefined : "secondary"}
                                            className="session-title"
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
