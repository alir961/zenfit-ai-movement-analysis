import { io, Socket } from "socket.io-client";

export const getPoseServerUrl = () => {
  return process.env.NEXT_PUBLIC_POSE_SERVER_URL ?? "http://localhost:8001";
};

export const createPoseSocket = (): Socket => {
  return io(getPoseServerUrl(), {
    transports: ["websocket"],
    autoConnect: true,
    // Keep retrying forever: the backend can take a while to load its models or
    // restart under the dev reloader, and a capped retry count leaves the page
    // offline until it is remounted.
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 2000,
  });
};
