import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient, ApiError } from '@/lib/api';
import { AgentPhase, TickLog, AuditLogEntry } from '@/types/api';

interface UseTradingSessionResult {
    phase: AgentPhase | string;
    lastTick: number;
    logs: TickLog[];
    auditLog: AuditLogEntry[];
    isLoading: boolean;
    isError: boolean;
    error: string | null;
    manualTick: () => Promise<void>;
    resetSession: () => Promise<void>;
}

export function useTradingSession(pollingInterval = 1000): UseTradingSessionResult {
    const [phase, setPhase] = useState<AgentPhase | string>(AgentPhase.IDLE);
    const [logs, setLogs] = useState<TickLog[]>([]);
    const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
    const [lastTick, setLastTick] = useState<number>(0);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [isError, setIsError] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    // Use a ref to track if we are currently fetching to avoid race conditions with fast polling
    const isFetchingRef = useRef(false);

    const fetchSessionStatus = useCallback(async () => {
        if (isFetchingRef.current) return;

        try {
            isFetchingRef.current = true;
            const data = await apiClient.getSessionStatus();

            // Update State
            if (data.state.phase) {
                setPhase(data.state.phase);
            }

            setLogs(data.logs);
            setAuditLog(data.audit_log || []);

            if (data.logs.length > 0) {
                // Assuming logs are chronologically ordered, or finding max tick
                const maxTick = Math.max(...data.logs.map(l => l.tick));
                setLastTick(maxTick);
            } else {
                // If no logs, maybe use current_index from session state if available
                if (data.state.current_bar_index !== undefined && data.state.current_bar_index !== null) {
                    setLastTick(data.state.current_bar_index);
                }
            }

            setIsError(false);
            setError(null);
        } catch (err: any) {
            console.error('Polling error:', err);
            setIsError(true);
            setError(err.message || 'Failed to sync with session');
        } finally {
            setIsLoading(false);
            isFetchingRef.current = false;
        }
    }, []);

    // Initial Fetch & Polling
    useEffect(() => {
        fetchSessionStatus();

        const intervalId = setInterval(fetchSessionStatus, pollingInterval);

        return () => clearInterval(intervalId);
    }, [fetchSessionStatus, pollingInterval]);

    const manualTick = async () => {
        try {
            await apiClient.advanceTick();
            // Immediately fetch status update
            await fetchSessionStatus();
        } catch (err: any) {
            // Handle 422 Agent Error specifically
            if (err instanceof ApiError && err.status === 422) {
                // In a real app with a toast provider, we would trigger it here.
                // e.g. toast({ title: "Agent Error", description: err.message, variant: "destructive" })
                console.error('Agent Execution Error:', err.message);
                setError(err.message); // Expose error to UI
            } else {
                console.error('Manual tick failed:', err);
                setError(err.message || 'Failed to advance tick');
            }
        }
    };

    const resetSession = async () => {
        try {
            setIsLoading(true);
            await apiClient.resetSession();
            // Reset local state
            setLogs([]);
            setAuditLog([]);
            setLastTick(0);
            await fetchSessionStatus();
        } catch (err: any) {
            console.error('Reset session failed:', err);
            setError(err.message || 'Failed to reset session');
        } finally {
            setIsLoading(false);
        }
    };

    return {
        phase,
        lastTick,
        logs,
        auditLog,
        isLoading,
        isError,
        error,
        manualTick,
        resetSession
    };
}
