"use client";

import { Mic, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/utils/toast";

export function VoiceRecorderButton({ disabled, onRecorded }: { disabled?: boolean; onRecorded: (file: File) => Promise<void> | void }) {
    const recorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const startedAtRef = useRef(0);
    const [recording, setRecording] = useState(false);
    const [seconds, setSeconds] = useState(0);

    useEffect(() => {
        if (!recording) return;
        const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - startedAtRef.current) / 1000)), 500);
        return () => window.clearInterval(timer);
    }, [recording]);

    useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), []);

    async function start() {
        if (disabled || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
            toast.error("Voice recording is not supported by this browser.");
            return;
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
            const preferred = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"].find((type) => MediaRecorder.isTypeSupported(type));
            const recorder = new MediaRecorder(stream, preferred ? { mimeType: preferred } : undefined);
            streamRef.current = stream;
            recorderRef.current = recorder;
            chunksRef.current = [];
            recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
            recorder.onstop = async () => {
                const mime = recorder.mimeType || "audio/webm";
                const blob = new Blob(chunksRef.current, { type: mime });
                stream.getTracks().forEach((track) => track.stop());
                streamRef.current = null;
                setRecording(false);
                setSeconds(0);
                if (blob.size < 500) { toast.error("The voice note was too short."); return; }
                const extension = mime.includes("ogg") ? "ogg" : mime.includes("mpeg") ? "mp3" : "webm";
                await onRecorded(new File([blob], `voice-note-${Date.now()}.${extension}`, { type: mime }));
            };
            recorder.start(500);
            startedAtRef.current = Date.now();
            setRecording(true);
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Microphone permission was denied.");
        }
    }

    function stop() {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    }

    return recording ? (
        <button type="button" onClick={stop} className="inline-flex h-11 min-w-11 items-center justify-center gap-2 rounded-xl bg-red-600 px-3 text-xs font-black text-white animate-pulse" title="Stop voice note">
            <Square className="h-4 w-4 fill-current" />{seconds}s
        </button>
    ) : (
        <button type="button" onClick={() => void start()} disabled={disabled} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border transition hover:border-primary hover:text-primary disabled:opacity-50" title="Record voice note" aria-label="Record voice note">
            <Mic className="h-5 w-5" />
        </button>
    );
}
