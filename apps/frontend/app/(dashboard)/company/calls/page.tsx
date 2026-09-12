"use client";

import {
  Activity,
  BadgeCheck,
  Clock3,
  Headphones,
  Mic2,
  PhoneCall,
  PhoneIncoming,
  PhoneOff,
  PhoneOutgoing,
  Radio,
  RefreshCcw,
  Save,
  Search,
  ShieldCheck,
  Square,
  Trash2,
  UsersRound,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { callsApi } from "@/api/calls";
import { CompanyPhoneBookPanel } from "@/components/calls/company-phonebook-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type {
  CallClient,
  CallClientDetail,
  CallDashboard,
  CallManagementPolicy,
  ClientCall,
  DesktopCallingCapability,
} from "@/types/calls";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type LiveKitTrack = {
  kind: string;
  attach: () => HTMLMediaElement;
};

type LiveKitLocalParticipant = {
  setMicrophoneEnabled: (enabled: boolean) => Promise<void>;
};

type LiveKitRoom = {
  connect: (url: string, token: string) => Promise<void>;
  disconnect: () => void;
  on: (event: string, handler: (...args: unknown[]) => void) => void;
  localParticipant: LiveKitLocalParticipant;
};

type LiveKitGlobal = {
  Room: new () => LiveKitRoom;
  RoomEvent: { TrackSubscribed: string };
  Track: { Kind: { Audio: string } };
};

declare global {
  interface Window {
    LivekitClient?: LiveKitGlobal;
  }
}

const LIVEKIT_BROWSER_SDK = "https://cdn.jsdelivr.net/npm/livekit-client@2.21.0/dist/livekit-client.umd.min.js";

function durationLabel(seconds: number | null | undefined) {
  const total = Math.max(0, Number(seconds ?? 0));
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function statusVariant(status: string) {
  if (["answered", "completed", "available", "active", "pass"].includes(status)) return "default" as const;
  if (["failed", "missed", "fail", "revoked", "deleted"].includes(status)) return "destructive" as const;
  return "secondary" as const;
}

function makeDesktopCallId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `desktop-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

async function loadLiveKitBrowserSdk(): Promise<LiveKitGlobal> {
  if (window.LivekitClient) return window.LivekitClient;
  await new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${LIVEKIT_BROWSER_SDK}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("LiveKit client could not be loaded")), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = LIVEKIT_BROWSER_SDK;
    script.async = true;
    script.crossOrigin = "anonymous";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("LiveKit client could not be loaded"));
    document.head.appendChild(script);
  });
  if (!window.LivekitClient) throw new Error("LiveKit browser client did not initialize");
  return window.LivekitClient;
}

export default function CallsAndQAPage() {
  const [dashboard, setDashboard] = useState<CallDashboard | null>(null);
  const [calls, setCalls] = useState<ClientCall[]>([]);
  const [liveCalls, setLiveCalls] = useState<ClientCall[]>([]);
  const [policy, setPolicy] = useState<CallManagementPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [search, setSearch] = useState("");
  const [direction, setDirection] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedCall, setSelectedCall] = useState<ClientCall | null>(null);
  const [reviewScore, setReviewScore] = useState("80");
  const [complianceStatus, setComplianceStatus] = useState("pass");
  const [customerCareStatus, setCustomerCareStatus] = useState("pass");
  const [reviewNotes, setReviewNotes] = useState("");
  const [callDescription, setCallDescription] = useState("");
  const [reviewSaving, setReviewSaving] = useState(false);
  const [descriptionSaving, setDescriptionSaving] = useState(false);
  const [deletingCallId, setDeletingCallId] = useState<string | null>(null);
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [monitoringCallId, setMonitoringCallId] = useState<string | null>(null);

  const [desktopCapability, setDesktopCapability] = useState<DesktopCallingCapability | null>(null);
  const [clientSearch, setClientSearch] = useState("");
  const [clientResults, setClientResults] = useState<CallClient[]>([]);
  const [clientSearching, setClientSearching] = useState(false);
  const [selectedClient, setSelectedClient] = useState<CallClientDetail | null>(null);
  const [selectedPhone, setSelectedPhone] = useState("");
  const [selectedLoanId, setSelectedLoanId] = useState("");
  const [calling, setCalling] = useState(false);
  const [activeDesktopCall, setActiveDesktopCall] = useState<ClientCall | null>(null);
  const [callMuted, setCallMuted] = useState(false);
  const [activeTab, setActiveTab] = useState("softphone");
  const searchParams = useSearchParams();
  const callQuery = searchParams.toString();
  const [prefilledCallContext, setPrefilledCallContext] = useState({
    borrowerId: "",
    loanId: "",
    phone: "",
  });
  const { borrowerId: prefilledBorrowerId, loanId: prefilledLoanId, phone: prefilledPhone } = prefilledCallContext;

  const monitorRoom = useRef<LiveKitRoom | null>(null);
  const desktopRoom = useRef<LiveKitRoom | null>(null);
  const monitorAudio = useRef<HTMLDivElement | null>(null);
  const desktopAudio = useRef<HTMLDivElement | null>(null);
  const handledCallContext = useRef<string | null>(null);

  const load = useCallback(async (showToast = false) => {
    setLoading(true);
    try {
      const [dashboardResult, callsResult, liveResult, policyResult] = await Promise.allSettled([
        callsApi.dashboard(),
        callsApi.listCalls({ limit: 500 }),
        callsApi.listLiveCalls(),
        callsApi.getPolicy(),
      ]);
      if (dashboardResult.status === "fulfilled") setDashboard(dashboardResult.value);
      if (callsResult.status === "fulfilled") setCalls(callsResult.value);
      if (liveResult.status === "fulfilled") setLiveCalls(liveResult.value);
      else setLiveCalls([]);
      if (policyResult.status === "fulfilled") setPolicy(policyResult.value);
      if (dashboardResult.status === "rejected" && callsResult.status === "rejected") throw dashboardResult.reason;
      if (showToast) toast.success("Call workspace refreshed.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Call management could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDesktopCapability = useCallback(async () => {
    try {
      setDesktopCapability(await callsApi.desktopCapability());
    } catch {
      setDesktopCapability(null);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(callQuery);
    const requestedTab = params.get("tab");
    setActiveTab(requestedTab === "phonebook" ? "phonebook" : "softphone");
    setPrefilledCallContext({
      borrowerId: params.get("borrower") ?? "",
      loanId: params.get("loan") ?? "",
      phone: params.get("phone") ?? "",
    });
  }, [callQuery]);

  useEffect(() => {
    void load();
    void loadDesktopCapability();
    return () => {
      monitorRoom.current?.disconnect();
      desktopRoom.current?.disconnect();
      if (recordingUrl) URL.revokeObjectURL(recordingUrl);
    };
    // recordingUrl is intentionally managed by the playback action.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, loadDesktopCapability]);

  const filteredCalls = useMemo(() => {
    const token = search.trim().toLowerCase();
    return calls.filter((call) => {
      if (direction !== "all" && call.direction !== direction) return false;
      if (statusFilter !== "all" && call.status !== statusFilter) return false;
      if (!token) return true;
      return [
        call.borrower_name,
        call.employee_name,
        call.phone_number,
        call.loan_reference,
        call.outcome,
        call.notes,
      ].filter(Boolean).join(" ").toLowerCase().includes(token);
    });
  }, [calls, direction, search, statusFilter]);

  async function playRecording(call: ClientCall) {
    if (!call.recording || call.recording.status !== "available") return;
    try {
      const blob = await callsApi.playRecording(call.recording.id);
      if (recordingUrl) URL.revokeObjectURL(recordingUrl);
      const url = URL.createObjectURL(blob);
      setRecordingUrl(url);
      chooseReview(call);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Recording could not be played."));
    }
  }

  function stopMonitoring() {
    monitorRoom.current?.disconnect();
    monitorRoom.current = null;
    if (monitorAudio.current) monitorAudio.current.replaceChildren();
    setMonitoringCallId(null);
  }

  async function startMonitoring(call: ClientCall) {
    try {
      stopMonitoring();
      const session = await callsApi.monitor(call.id);
      const livekit = await loadLiveKitBrowserSdk();
      const room = new livekit.Room();
      room.on(livekit.RoomEvent.TrackSubscribed, (...args: unknown[]) => {
        const track = args[0] as LiveKitTrack;
        if (track.kind !== livekit.Track.Kind.Audio) return;
        const element = track.attach();
        element.autoplay = true;
        element.controls = false;
        monitorAudio.current?.appendChild(element);
      });
      await room.connect(session.server_url, session.token);
      monitorRoom.current = room;
      setMonitoringCallId(call.id);
      toast.success("Listen-only monitoring connected.");
    } catch (error: unknown) {
      stopMonitoring();
      toast.error(getErrorMessage(error, "Live monitoring could not connect."));
    }
  }

  function chooseReview(call: ClientCall) {
    setSelectedCall(call);
    const mine = call.quality_reviews[0];
    setReviewScore(String(mine?.score ?? 80));
    setComplianceStatus(mine?.compliance_status ?? "pass");
    setCustomerCareStatus(mine?.customer_care_status ?? "pass");
    setReviewNotes(mine?.notes ?? "");
    setCallDescription(call.notes ?? "");
  }

  async function saveReview() {
    if (!selectedCall) return;
    const score = Number(reviewScore);
    if (!Number.isFinite(score) || score < 0 || score > 100) {
      toast.error("Quality score must be between 0 and 100.");
      return;
    }
    setReviewSaving(true);
    try {
      await callsApi.qualityReview(selectedCall.id, {
        score,
        compliance_status: complianceStatus,
        customer_care_status: customerCareStatus,
        notes: reviewNotes.trim() || null,
      });
      toast.success("Quality review saved.");
      const updated = await callsApi.getCall(selectedCall.id);
      chooseReview(updated);
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Quality review could not be saved."));
    } finally {
      setReviewSaving(false);
    }
  }

  async function saveCallDescription() {
    if (!selectedCall) return;
    setDescriptionSaving(true);
    try {
      const updated = await callsApi.updateDescription(selectedCall.id, callDescription.trim() || null);
      chooseReview(updated);
      await load();
      toast.success("Your call description was saved.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Only the employee who made this call can edit its description."));
    } finally {
      setDescriptionSaving(false);
    }
  }

  async function removeCall(call: ClientCall) {
    if (!window.confirm("Delete this call record and its recording permanently? This cannot be undone.")) return;
    setDeletingCallId(call.id);
    try {
      await callsApi.deleteCall(call.id);
      if (selectedCall?.id === call.id) setSelectedCall(null);
      if (recordingUrl) {
        URL.revokeObjectURL(recordingUrl);
        setRecordingUrl(null);
      }
      await load();
      toast.success("The call record and its recording were deleted.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Only the company owner can delete this call. A legal hold also prevents deletion."));
    } finally {
      setDeletingCallId(null);
    }
  }

  async function savePolicy() {
    if (!policy) return;
    setSavingPolicy(true);
    try {
      const updated = await callsApi.updatePolicy({
        recording_enabled: policy.recording_enabled,
        recording_retention_days: Number(policy.recording_retention_days),
        call_metadata_retention_months: Number(policy.call_metadata_retention_months),
        automatic_deletion_enabled: policy.automatic_deletion_enabled,
        live_monitoring_enabled: policy.live_monitoring_enabled,
        manager_downloads_enabled: policy.manager_downloads_enabled,
        legal_hold_enabled: policy.legal_hold_enabled,
        recording_notice: policy.recording_notice,
      });
      setPolicy(updated);
      await loadDesktopCapability();
      toast.success("Call policy saved.");
      await load();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Only company management can change this policy."));
    } finally {
      setSavingPolicy(false);
    }
  }

  async function findClients() {
    setClientSearching(true);
    try {
      setClientResults(await callsApi.listClients(clientSearch.trim() || undefined));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Clients could not be searched."));
    } finally {
      setClientSearching(false);
    }
  }

  const selectCallClient = useCallback(async (
    borrowerId: string,
    preferredPhone = "",
    preferredLoanId = "",
  ) => {
    try {
      const details = await callsApi.getClient(borrowerId);
      setSelectedClient(details);
      const permittedContacts = details.contacts.filter((contact) => contact.is_call_permitted);
      const requestedContact = permittedContacts.find((contact) => contact.phone === preferredPhone);
      const preferred = requestedContact
        ?? permittedContacts.find((contact) => contact.is_primary)
        ?? permittedContacts[0];
      setSelectedPhone(preferred?.phone ?? "");
      setSelectedLoanId(details.loans.some((loan) => loan.id === preferredLoanId)
        ? preferredLoanId
        : details.loans[0]?.id ?? "");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The borrower profile could not be loaded."));
    }
  }, []);

  async function chooseClient(client: CallClient) {
    await selectCallClient(client.borrower_id);
  }

  const startPhonebookCall = useCallback((context: {
    borrowerId: string;
    phone: string;
    loanId?: string;
  }) => {
    setClientResults([]);
    setActiveTab("softphone");
    void selectCallClient(context.borrowerId, context.phone, context.loanId ?? "");
  }, [selectCallClient]);

  useEffect(() => {
    if (!prefilledBorrowerId) return;
    const contextKey = [prefilledBorrowerId, prefilledLoanId, prefilledPhone].join("|");
    if (handledCallContext.current === contextKey) return;
    handledCallContext.current = contextKey;
    void selectCallClient(prefilledBorrowerId, prefilledPhone, prefilledLoanId);
  }, [prefilledBorrowerId, prefilledLoanId, prefilledPhone, selectCallClient]);

  function disconnectDesktopRoom() {
    desktopRoom.current?.disconnect();
    desktopRoom.current = null;
    if (desktopAudio.current) desktopAudio.current.replaceChildren();
    setCallMuted(false);
  }

  async function startDesktopCall() {
    if (!selectedClient || !selectedPhone) {
      toast.error("Select a borrower contact before calling.");
      return;
    }
    if (!desktopCapability?.calling_available) {
      toast.error("Laptop calling is awaiting the company’s controlled One Connect/SIP configuration.");
      return;
    }

    setCalling(true);
    let createdCall: ClientCall | null = null;
    try {
      createdCall = await callsApi.createCall({
        device_call_uuid: makeDesktopCallId(),
        phone_number: selectedPhone,
        direction: "outgoing",
        started_at: new Date().toISOString(),
        borrower_id: selectedClient.borrower_id,
        loan_id: selectedLoanId || null,
        status: "started",
      });

      const session = await callsApi.employeeMediaToken(createdCall.id);
      const livekit = await loadLiveKitBrowserSdk();
      const room = new livekit.Room();
      room.on(livekit.RoomEvent.TrackSubscribed, (...args: unknown[]) => {
        const track = args[0] as LiveKitTrack;
        if (track.kind !== livekit.Track.Kind.Audio) return;
        const element = track.attach();
        element.autoplay = true;
        element.controls = false;
        desktopAudio.current?.appendChild(element);
      });
      await room.connect(session.server_url, session.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      desktopRoom.current = room;

      const dialing = await callsApi.dial(createdCall.id);
      setActiveDesktopCall({ ...createdCall, status: dialing.status, is_live: true });
      toast.success("Calling through LoanHub.");
      await load();
    } catch (error: unknown) {
      disconnectDesktopRoom();
      if (createdCall) await callsApi.hangup(createdCall.id).catch(() => undefined);
      toast.error(getErrorMessage(error, "Laptop call could not start."));
      await load();
    } finally {
      setCalling(false);
    }
  }

  async function endDesktopCall() {
    if (!activeDesktopCall) return;
    try {
      await callsApi.hangup(activeDesktopCall.id);
      disconnectDesktopRoom();
      setActiveDesktopCall(null);
      await load();
      toast.success("Call ended. The controlled recording will appear when the provider saves it.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "LoanHub could not end the call."));
    }
  }

  async function toggleMute() {
    if (!desktopRoom.current) return;
    const nextMuted = !callMuted;
    try {
      await desktopRoom.current.localParticipant.setMicrophoneEnabled(!nextMuted);
      setCallMuted(nextMuted);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Microphone state could not be changed."));
    }
  }

  const summary = dashboard?.summary;
  const metrics = [
    { label: "Today's calls", value: summary?.today_calls ?? 0, icon: PhoneCall },
    { label: "Incoming", value: summary?.incoming ?? 0, icon: PhoneIncoming },
    { label: "Outgoing", value: summary?.outgoing ?? 0, icon: PhoneOutgoing },
    { label: "Clients contacted", value: summary?.clients_contacted ?? 0, icon: UsersRound },
    { label: "Live calls", value: summary?.live_calls ?? 0, icon: Activity },
    { label: "Recordings", value: summary?.recordings_available ?? 0, icon: Mic2 },
  ];

  return (
    <div className="space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-3xl font-black tracking-tight">Calls & QA</h1>
            <Badge variant={desktopCapability?.calling_available ? "default" : "secondary"}>
              {desktopCapability?.calling_available ? "Laptop calling ready" : "Controlled calling setup required"}
            </Badge>
          </div>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Call borrowers from a laptop, keep recordings under company controls, and review every authorised call in one place.
          </p>
        </div>
        <Button variant="outline" onClick={() => { void load(true); void loadDesktopCapability(); }} disabled={loading}>
          <RefreshCcw className={"mr-2 h-4 w-4 " + (loading ? "animate-spin" : "")} /> Refresh
        </Button>
      </div>

      {!desktopCapability?.calling_available && (
        <Card className="border-dashed">
          <CardContent className="flex gap-3 p-4 text-sm text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
            <span>
              Laptop calling becomes available after the company subscribes to the controlled calling service and LoanHub is configured with its Vodacom One Connect/SIP route and LiveKit media service. No SIP password is exposed to a browser.
            </span>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        {metrics.map((item) => (
          <Card key={item.label}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{item.label}</p>
                  <p className="mt-2 text-2xl font-black">{item.value}</p>
                </div>
                <item.icon className="h-6 w-6 text-primary" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-5">
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="softphone">Desktop phone</TabsTrigger>
          <TabsTrigger value="phonebook">Phone book</TabsTrigger>
          <TabsTrigger value="calls">Call register</TabsTrigger>
          <TabsTrigger value="live">Live calls</TabsTrigger>
          <TabsTrigger value="performance">Employee performance</TabsTrigger>
          <TabsTrigger value="review">Recording & QA</TabsTrigger>
          <TabsTrigger value="policy">Policy & retention</TabsTrigger>
        </TabsList>

        <TabsContent value="phonebook" className="space-y-4">
          <CompanyPhoneBookPanel onStartCall={startPhonebookCall} />
        </TabsContent>

        <TabsContent value="softphone" className="space-y-4">
          <div ref={desktopAudio} className="hidden" aria-hidden="true" />
          <Card className={activeDesktopCall ? "border-primary/50" : undefined}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><PhoneCall className="h-5 w-5 text-primary" /> LoanHub desktop phone</CardTitle>
              <CardDescription>
                Calls go through the company’s controlled One Connect/SIP service. The borrower receives a normal telephone call; they do not need LoanHub.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {activeDesktopCall ? (
                <div className="rounded-xl bg-muted/40 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2"><Radio className="h-4 w-4 animate-pulse text-primary" /><p className="font-black">Calling {activeDesktopCall.borrower_name ?? activeDesktopCall.phone_number}</p></div>
                      <p className="mt-1 text-sm text-muted-foreground">{activeDesktopCall.phone_number} · Recording: {titleCase(activeDesktopCall.recording_status)}</p>
                    </div>
                    <Badge>LIVE</Badge>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-3">
                    <Button variant="outline" onClick={() => void toggleMute()}>
                      {callMuted ? <Volume2 className="mr-2 h-4 w-4" /> : <VolumeX className="mr-2 h-4 w-4" />}
                      {callMuted ? "Unmute" : "Mute"}
                    </Button>
                    <Button variant="destructive" onClick={() => void endDesktopCall()}>
                      <PhoneOff className="mr-2 h-4 w-4" /> End call
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="rounded-xl bg-muted/40 p-4 text-sm text-muted-foreground">
                  Choose an authorised borrower and a permitted contact. Calls automatically create a LoanHub call record before the external number is dialled.
                </p>
              )}

              <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input value={clientSearch} onChange={(event) => setClientSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void findClients(); }} placeholder="Search borrower name, phone or loan reference" className="pl-9" />
                </div>
                <Button variant="outline" onClick={() => void findClients()} disabled={clientSearching || Boolean(activeDesktopCall)}>
                  <Search className="mr-2 h-4 w-4" /> {clientSearching ? "Searching…" : "Find client"}
                </Button>
              </div>

              {clientResults.length > 0 && !selectedClient && (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {clientResults.map((client) => (
                    <button key={client.borrower_id} type="button" onClick={() => void chooseClient(client)} className="rounded-xl border p-4 text-left transition hover:border-primary hover:bg-muted/30">
                      <p className="font-black">{client.name ?? "Borrower"}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{client.phone ?? "No primary number"}</p>
                      <p className="mt-2 text-xs text-muted-foreground">{client.loans.map((loan) => loan.loan_reference).join(" · ") || "No loan reference"}</p>
                    </button>
                  ))}
                </div>
              )}

              {selectedClient && (
                <div className="space-y-4 rounded-xl border p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div><p className="text-lg font-black">{selectedClient.name ?? "Borrower"}</p><p className="text-sm text-muted-foreground">Borrower profile, loans and authorised calling contacts</p></div>
                    <Button variant="ghost" size="sm" onClick={() => { setSelectedClient(null); setSelectedPhone(""); setSelectedLoanId(""); }}>Change client</Button>
                  </div>
                  <div className="grid gap-4 lg:grid-cols-2">
                    <div>
                      <Label htmlFor="desktop-contact">Contact to call</Label>
                      <NativeSelect id="desktop-contact" value={selectedPhone} onChange={(event) => setSelectedPhone(event.target.value)} disabled={Boolean(activeDesktopCall)}>
                        <option value="">Select a permitted contact</option>
                        {selectedClient.contacts.filter((contact) => contact.is_call_permitted).map((contact) => (
                          <option key={contact.phone + contact.name} value={contact.phone}>{contact.name} · {contact.relationship} · {contact.phone}</option>
                        ))}
                      </NativeSelect>
                      {!selectedClient.contacts.some((contact) => contact.is_call_permitted) && <p className="mt-2 text-xs text-destructive">No authorised calling contact is recorded for this borrower.</p>}
                    </div>
                    <div>
                      <Label htmlFor="desktop-loan">Related loan</Label>
                      <NativeSelect id="desktop-loan" value={selectedLoanId} onChange={(event) => setSelectedLoanId(event.target.value)} disabled={Boolean(activeDesktopCall)}>
                        <option value="">No specific loan</option>
                        {selectedClient.loans.map((loan) => <option key={loan.id} value={loan.id}>{loan.loan_reference} · {formatMoney(loan.balance)} · {titleCase(loan.status)}</option>)}
                      </NativeSelect>
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {selectedClient.loans.map((loan) => (
                      <div key={loan.id} className="rounded-xl bg-muted/40 p-3"><p className="font-bold">{loan.loan_reference}</p><p className="mt-1 text-sm">{formatMoney(loan.balance)}</p><p className="mt-1 text-xs text-muted-foreground">{titleCase(loan.status)}{loan.is_overdue ? " · overdue" : ""}</p></div>
                    ))}
                  </div>
                  <Button className="w-full sm:w-auto" disabled={calling || Boolean(activeDesktopCall) || !selectedPhone || !desktopCapability?.calling_available} onClick={() => void startDesktopCall()}>
                    <PhoneCall className="mr-2 h-4 w-4" /> {calling ? "Connecting…" : "Call from laptop"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="calls" className="space-y-4">
          <Card>
            <CardContent className="grid gap-3 p-4 lg:grid-cols-[1fr_180px_180px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search client, employee, loan, phone, outcome…" className="pl-9" />
              </div>
              <NativeSelect value={direction} onChange={(event) => setDirection(event.target.value)}>
                <option value="all">All directions</option><option value="incoming">Incoming</option><option value="outgoing">Outgoing</option>
              </NativeSelect>
              <NativeSelect value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All statuses</option><option value="started">Started</option><option value="ringing">Ringing</option><option value="answered">Answered</option><option value="completed">Completed</option><option value="missed">Missed</option><option value="failed">Failed</option>
              </NativeSelect>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Company call & recording library</CardTitle><CardDescription>{filteredCalls.length} calls match the current filters. Company owners, admins and branch managers can listen within their authorised scope.</CardDescription></CardHeader>
            <CardContent className="overflow-x-auto p-0">
              <table className="w-full min-w-[1180px] text-sm">
                <thead className="border-y bg-muted/40 text-left text-xs uppercase text-muted-foreground"><tr><th className="px-5 py-3">Client / loan</th><th className="px-5 py-3">Employee</th><th className="px-5 py-3">Direction</th><th className="px-5 py-3">Started</th><th className="px-5 py-3">Duration</th><th className="px-5 py-3">Outcome</th><th className="px-5 py-3">Recording</th><th className="px-5 py-3">Actions</th></tr></thead>
                <tbody>
                  {filteredCalls.map((call) => (
                    <tr key={call.id} className="border-b align-top hover:bg-muted/20">
                      <td className="px-5 py-4"><p className="font-bold">{call.borrower_name ?? "Unknown caller"}</p><p className="text-xs text-muted-foreground">{call.phone_number}</p>{call.loan_reference && <p className="mt-1 text-xs">{call.loan_reference} · {call.loan_balance !== null ? formatMoney(call.loan_balance) : ""}</p>}</td>
                      <td className="px-5 py-4">{call.employee_name ?? "Employee"}</td>
                      <td className="px-5 py-4"><Badge variant="outline">{titleCase(call.direction)}</Badge></td>
                      <td className="px-5 py-4">{call.started_at ? formatDateTime(call.started_at) : "—"}</td>
                      <td className="px-5 py-4 font-mono">{durationLabel(call.duration_seconds)}</td>
                      <td className="px-5 py-4"><Badge variant={statusVariant(call.status)}>{titleCase(call.status)}</Badge>{call.outcome && <p className="mt-2 text-xs text-muted-foreground">{titleCase(call.outcome)}</p>}</td>
                      <td className="px-5 py-4">{call.recording?.status === "available" ? <Button size="sm" variant="outline" onClick={() => void playRecording(call)}><Headphones className="mr-2 h-4 w-4" /> Listen</Button> : <Badge variant="secondary">{titleCase(call.recording_status)}</Badge>}</td>
                      <td className="px-5 py-4"><div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => chooseReview(call)}><BadgeCheck className="mr-2 h-4 w-4" /> Details</Button>{call.permissions?.can_delete && <Button size="sm" variant="destructive" disabled={deletingCallId === call.id} onClick={() => void removeCall(call)}><Trash2 className="mr-2 h-4 w-4" /> {deletingCallId === call.id ? "Deleting…" : "Delete"}</Button>}</div></td>
                    </tr>
                  ))}
                  {!filteredCalls.length && <tr><td colSpan={8} className="px-5 py-12 text-center text-muted-foreground">No calls match the current filters.</td></tr>}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="live" className="space-y-4">
          <div ref={monitorAudio} className="hidden" aria-hidden="true" />
          {monitoringCallId && <Card className="border-primary/40"><CardContent className="flex flex-wrap items-center justify-between gap-4 p-5"><div className="flex items-center gap-3"><Headphones className="h-5 w-5 text-primary" /><div><p className="font-black">Listen-only monitoring active</p><p className="text-sm text-muted-foreground">Your browser cannot publish audio into this call.</p></div></div><Button variant="outline" onClick={stopMonitoring}><Square className="mr-2 h-4 w-4" /> Stop listening</Button></CardContent></Card>}
          <div className="grid gap-4 lg:grid-cols-2">
            {liveCalls.map((call) => <Card key={call.id}><CardContent className="p-5"><div className="flex items-start justify-between gap-4"><div><p className="text-lg font-black">{call.borrower_name ?? call.phone_number}</p><p className="text-sm text-muted-foreground">{call.employee_name} · {titleCase(call.direction)}</p><p className="mt-3 font-mono text-xl">{durationLabel(call.duration_seconds)}</p></div><Badge>LIVE</Badge></div><Button className="mt-5 w-full" disabled={!dashboard?.media_configured || monitoringCallId === call.id} onClick={() => void startMonitoring(call)}><Headphones className="mr-2 h-4 w-4" /> {monitoringCallId === call.id ? "Listening" : "Listen live"}</Button></CardContent></Card>)}
            {!liveCalls.length && <Card><CardContent className="p-10 text-center text-muted-foreground">There are no active calls in your permitted scope.</CardContent></Card>}
          </div>
        </TabsContent>

        <TabsContent value="performance">
          <Card><CardHeader><CardTitle>Employee call performance</CardTitle><CardDescription>Today’s activity in the manager’s permitted company and branch scope.</CardDescription></CardHeader><CardContent className="overflow-x-auto p-0"><table className="w-full min-w-[800px] text-sm"><thead className="border-y bg-muted/40 text-left text-xs uppercase text-muted-foreground"><tr><th className="px-5 py-3">Employee</th><th className="px-5 py-3">Calls</th><th className="px-5 py-3">Incoming</th><th className="px-5 py-3">Outgoing</th><th className="px-5 py-3">Clients</th><th className="px-5 py-3">Recordings</th><th className="px-5 py-3">Avg duration</th></tr></thead><tbody>{(dashboard?.employee_performance ?? []).map((item) => <tr key={item.staff_id} className="border-b"><td className="px-5 py-4 font-bold">{item.employee_name ?? "Employee"}</td><td className="px-5 py-4">{item.total_calls}</td><td className="px-5 py-4">{item.incoming}</td><td className="px-5 py-4">{item.outgoing}</td><td className="px-5 py-4">{item.clients_contacted}</td><td className="px-5 py-4">{item.recordings}</td><td className="px-5 py-4 font-mono">{durationLabel(item.average_duration_seconds)}</td></tr>)}{!(dashboard?.employee_performance?.length) && <tr><td colSpan={7} className="px-5 py-10 text-center text-muted-foreground">No employee call activity is available for today.</td></tr>}</tbody></table></CardContent></Card>
        </TabsContent>

        <TabsContent value="review" className="grid gap-5 xl:grid-cols-[1fr_420px]">
          <Card><CardHeader><CardTitle>Call record and recording</CardTitle><CardDescription>Select Details from the call register. Only the employee who made a call may amend its description.</CardDescription></CardHeader><CardContent>{selectedCall ? <div className="space-y-4"><div className="grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-muted/40 p-4"><p className="text-xs font-bold uppercase text-muted-foreground">Client</p><p className="mt-1 font-black">{selectedCall.borrower_name ?? "Unknown caller"}</p><p className="text-sm">{selectedCall.phone_number}</p></div><div className="rounded-xl bg-muted/40 p-4"><p className="text-xs font-bold uppercase text-muted-foreground">Employee</p><p className="mt-1 font-black">{selectedCall.employee_name}</p><p className="text-sm">{selectedCall.loan_reference ?? "No loan linked"}</p></div></div>{recordingUrl && <audio src={recordingUrl} controls autoPlay className="w-full" />}{selectedCall.permissions?.can_edit_description ? <div className="space-y-2"><Label htmlFor="call-description">Your call description</Label><Textarea id="call-description" value={callDescription} onChange={(event) => setCallDescription(event.target.value)} rows={5} placeholder="What was discussed, promise made, or follow-up needed…" /><Button variant="outline" disabled={descriptionSaving} onClick={() => void saveCallDescription()}><Save className="mr-2 h-4 w-4" /> {descriptionSaving ? "Saving…" : "Save description"}</Button></div> : <div className="rounded-xl border p-4"><p className="text-xs font-bold uppercase text-muted-foreground">Caller’s description</p><p className="mt-2 text-sm">{selectedCall.notes || "No description was recorded."}</p></div>}<div><p className="text-xs font-bold uppercase text-muted-foreground">Quality reviews</p><div className="mt-2 space-y-2">{selectedCall.quality_reviews.map((review) => <div key={review.id} className="rounded-xl border p-3"><div className="flex items-center justify-between"><span className="font-bold">{review.reviewer_name ?? "Reviewer"}</span><Badge>{review.score}/100</Badge></div><p className="mt-1 text-xs text-muted-foreground">Compliance: {titleCase(review.compliance_status)} · Customer care: {titleCase(review.customer_care_status)}</p>{review.notes && <p className="mt-2 text-sm">{review.notes}</p>}</div>)}{!selectedCall.quality_reviews.length && <p className="text-sm text-muted-foreground">No QA review has been saved yet.</p>}</div></div></div> : <p className="py-16 text-center text-muted-foreground">Choose a call from the register.</p>}</CardContent></Card>
          <Card><CardHeader><CardTitle>Quality score</CardTitle><CardDescription>Audited QA assessment for the selected employee call.</CardDescription></CardHeader><CardContent className="space-y-4"><div><Label htmlFor="qa-score">Score / 100</Label><Input id="qa-score" type="number" min={0} max={100} value={reviewScore} onChange={(event) => setReviewScore(event.target.value)} /></div><div><Label>Compliance</Label><NativeSelect value={complianceStatus} onChange={(event) => setComplianceStatus(event.target.value)}><option value="pass">Pass</option><option value="needs_improvement">Needs improvement</option><option value="fail">Fail</option><option value="not_assessed">Not assessed</option></NativeSelect></div><div><Label>Customer care</Label><NativeSelect value={customerCareStatus} onChange={(event) => setCustomerCareStatus(event.target.value)}><option value="pass">Pass</option><option value="needs_improvement">Needs improvement</option><option value="fail">Fail</option><option value="not_assessed">Not assessed</option></NativeSelect></div><div><Label htmlFor="qa-notes">Review notes</Label><Textarea id="qa-notes" value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} rows={6} placeholder="Coaching, compliance or service observations…" /></div><Button className="w-full" disabled={!selectedCall || reviewSaving} onClick={() => void saveReview()}><Save className="mr-2 h-4 w-4" /> Save QA review</Button></CardContent></Card>
        </TabsContent>

        <TabsContent value="policy">
          <Card><CardHeader><CardTitle>Recording, monitoring & retention policy</CardTitle><CardDescription>Server-side company controls. Playback never extends the deletion date.</CardDescription></CardHeader><CardContent className="space-y-6">{policy ? <><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{[["Recording enabled", "recording_enabled"], ["Automatic deletion", "automatic_deletion_enabled"], ["Live monitoring", "live_monitoring_enabled"], ["Legal hold", "legal_hold_enabled"]].map(([label, key]) => <label key={key} className="flex items-center justify-between rounded-xl border p-4 text-sm font-bold">{label}<input type="checkbox" className="h-5 w-5" checked={Boolean(policy[key as keyof CallManagementPolicy])} onChange={(event) => setPolicy({ ...policy, [key]: event.target.checked })} /></label>)}</div><div className="grid gap-4 md:grid-cols-2"><div><Label htmlFor="retention-days">Recording retention days</Label><Input id="retention-days" type="number" min={1} max={3650} value={policy.recording_retention_days} onChange={(event) => setPolicy({ ...policy, recording_retention_days: Number(event.target.value) })} /></div><div><Label htmlFor="metadata-months">Call metadata retention months</Label><Input id="metadata-months" type="number" min={1} max={120} value={policy.call_metadata_retention_months} onChange={(event) => setPolicy({ ...policy, call_metadata_retention_months: Number(event.target.value) })} /></div></div><div><Label htmlFor="recording-notice">Recording notice</Label><Textarea id="recording-notice" rows={4} value={policy.recording_notice ?? ""} onChange={(event) => setPolicy({ ...policy, recording_notice: event.target.value })} /></div><div className="flex items-center justify-between rounded-xl bg-muted/40 p-4"><div className="flex gap-3"><Clock3 className="h-5 w-5 text-primary" /><div><p className="font-bold">Retention is based on recording creation time</p><p className="text-sm text-muted-foreground">Playing a recording does not reset or extend its scheduled deletion.</p></div></div></div><Button onClick={() => void savePolicy()} disabled={savingPolicy}><Save className="mr-2 h-4 w-4" /> Save company policy</Button></> : <p className="text-muted-foreground">Policy settings are unavailable for this active role.</p>}</CardContent></Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
