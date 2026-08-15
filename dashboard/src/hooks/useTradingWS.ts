"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface WSMessage {
  type: string;
  symbol?: string;
  timeframe?: string;
  mode?: string;
  decision?: any;
  technical_summary?: any;
  execution?: any;
  closed_count?: number;
  message?: string;
  timestamp?: number;
}

export function useTradingWS(onMessageReceived?: (msg: WSMessage) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (typeof window === "undefined") return;

    // Use backend port 8001 for WS
    const wsUrl = `ws://${window.location.hostname}:8001/api/trading/ws`;

    try {
      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setIsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const data: WSMessage = JSON.parse(event.data);
          if (onMessageReceived) {
            onMessageReceived(data);
          }
        } catch (e) {
          console.error("Failed to parse WS JSON:", e);
        }
      };

      socket.onclose = () => {
        setIsConnected(false);
        setTimeout(connect, 3000);
      };

      socket.onerror = () => {
        setIsConnected(false);
        socket.close();
      };

      wsRef.current = socket;
    } catch (e) {
      console.error("WS connection error:", e);
      setTimeout(connect, 3000);
    }
  }, [onMessageReceived]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { isConnected };
}
