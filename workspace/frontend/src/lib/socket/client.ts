import { io, Socket } from "socket.io-client";

export const getPoseServerUrl = () => {
  return process.env.NEXT_PUBLIC_POSE_SERVER_URL ?? "http://localhost:8001";
};

export const createPoseSocket = (): Socket => {
  return io(getPoseServerUrl(), {
    transports: ["websocket"],
    autoConnect: true,
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 500,
  });
};
