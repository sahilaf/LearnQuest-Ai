/**
 * TutorPage - OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
 * See plan.md §6.3, §6.6, §6.7.
 *
 * Three ways to work with one tutor, Redwan, one tab each:
 *   Live   - talk out loud, like a call (Gemini Live)
 *   Teach  - Teach-Back: explain a concept to Redwan, who holds your old mistake
 *   Chat   - a text chatbot with history
 *
 * Calm by default: opening the page connects nothing and plays nothing. The
 * avatar connects only when the student presses Connect; a live call starts
 * only when they press Start.
 *
 * One tutor, not three: Live and Chat share the selected conversation (live
 * turns are saved into it), all three use the same male voice, and the avatar
 * connection is shared by Live and Teach.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { BookOpen, GraduationCap, MessageSquare, Plus, Radio, Trash2 } from 'lucide-react';

import ChatPanel from '../../components/tutor/ChatPanel';
import { Button, Select } from '../../components/ui';
import { createConversation, deleteConversation, listConversations } from '../../api/tutor';
import { getLesson } from '../../api/lessons';
import LivePanel, { LiveControls } from './LivePanel';
import { liveStateOf } from './LiveStatus';
import { TeachChallenge, TeachConversation } from './TeachBackPanel';
import TutorStage from './TutorStage';
import useLiveConversation from './useLiveConversation';
import useTeachBack, { TEACH_PHASE } from './useTeachBack';
import useTutorVoice from './useTutorVoice';

const TABS = [
  { id: 'live', label: 'Live conversation', short: 'Live', icon: Radio },
  { id: 'teach', label: 'Teach Redwan', short: 'Teach', icon: GraduationCap },
  { id: 'chat', label: 'Chat', short: 'Chat', icon: MessageSquare },
];

function initialTab(searchParams) {
  const tab = searchParams.get('tab');
  if (TABS.some((t) => t.id === tab)) return tab;
  if (searchParams.get('mode') === 'teachback') return 'teach';
  return 'live';
}

export default function TutorPage() {
  const { conversationId: routeConvRef } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const lessonId = searchParams.get('lessonId') || searchParams.get('lesson_id');
  const topicParam = searchParams.get('topic');

  const [tab, setTab] = useState(() => initialTab(searchParams));
  const [lesson, setLesson] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [selectedConvRef, setSelectedConvRef] = useState(routeConvRef || null);

  // Avatar: opt-in, shared by Live and Teach.
  const [avatarConnected, setAvatarConnected] = useState(false);
  const [avatarLive, setAvatarLive] = useState(false);
  const avatarRef = useRef(null);
  const [muted, setMuted] = useState(false);

  // Speak through the face whenever video is connected - it is on screen
  // in every tab.
  const voice = useTutorVoice({
    avatarRef,
    useAvatar: avatarLive,
    muted,
  });
  const live = useLiveConversation({ voice });
  // Redwan speaks Teach lines only while the Teach tab is open.
  const tabRef = useRef(tab);
  tabRef.current = tab;
  const teach = useTeachBack({
    initialTopic: topicParam,
    speak: (text) => { if (tabRef.current === 'teach') voice.speakText(text); },
  });

  // Is Redwan audible right now (face or voice-only)? Polled, because the
  // audio clock is not React state; drives the one status chip.
  const [speakingNow, setSpeakingNow] = useState(false);
  const voiceRef = useRef(voice);
  voiceRef.current = voice;
  useEffect(() => {
    const id = setInterval(() => {
      const v = voiceRef.current;
      setSpeakingNow(v.isAudible() || v.synthesizing);
    }, 200);
    return () => clearInterval(id);
  }, []);

  useEffect(() => { if (routeConvRef) setSelectedConvRef(routeConvRef); }, [routeConvRef]);

  useEffect(() => {
    if (!lessonId) { setLesson(null); return; }
    getLesson(lessonId).then(setLesson).catch(() => setLesson(null));
  }, [lessonId]);

  const fetchConversations = useCallback(async () => {
    try {
      const res = await listConversations({ page: 1, page_size: 30 });
      setConversations(res?.items || (Array.isArray(res) ? res : []));
    } catch {
      /* the list is a convenience; the tabs still work without it */
    } finally {
      setLoadingConversations(false);
    }
  }, []);
  useEffect(() => { fetchConversations(); }, [fetchConversations]);

  const selectedConv = useMemo(
    () => conversations.find((c) => String(c.number) === String(selectedConvRef)) || null,
    [conversations, selectedConvRef],
  );

  const selectConversation = useCallback((ref) => {
    setSelectedConvRef(ref);
    navigate(ref ? `/tutor/${ref}${window.location.search}` : `/tutor${window.location.search}`, { replace: true });
  }, [navigate]);

  const newConversation = useCallback(async (title = 'New conversation') => {
    const created = await createConversation({ title, lesson_id: lessonId || undefined });
    setConversations((prev) => [created, ...prev]);
    selectConversation(created.number);
    return created;
  }, [lessonId, selectConversation]);

  const removeConversation = async (e, ref) => {
    e.stopPropagation();
    if (!window.confirm('Delete this conversation?')) return;
    try {
      await deleteConversation(ref);
      const remaining = conversations.filter((c) => String(c.number) !== String(ref));
      setConversations(remaining);
      if (String(selectedConvRef) === String(ref)) selectConversation(remaining[0]?.number || null);
    } catch {
      /* leave it listed; nothing was deleted */
    }
  };

  const switchTab = (next) => {
    if (next === tab) return;
    // A call belongs to the Live tab; leaving it hangs up rather than leaving
    // a hidden microphone open. Speech from the old tab stops too.
    if (tab === 'live') live.stop();
    voice.stop();
    setTab(next);
    const params = new URLSearchParams(searchParams);
    params.set('tab', next);
    params.delete('mode');
    setSearchParams(params, { replace: true });
  };

  const startLive = async () => {
    avatarRef.current?.resume?.();
    let ref = selectedConvRef;
    if (!ref) {
      try {
        ref = (await newConversation('Live conversation')).number;
      } catch {
        ref = null; // the call still works; it just is not saved
      }
    }
    live.start(ref);
  };

  // After a call the conversation has new turns and probably a new title.
  const prevLiveStatus = useRef(live.status);
  useEffect(() => {
    if (prevLiveStatus.current !== live.status && live.status !== 'live' && live.status !== 'connecting') {
      fetchConversations();
    }
    prevLiveStatus.current = live.status;
  }, [live.status, fetchConversations]);

  const disconnectAvatar = useCallback(() => {
    avatarRef.current?.stopNow();
    setAvatarConnected(false);
    setAvatarLive(false);
  }, []);

  const inCall = live.status === 'live' || live.status === 'connecting';

  // One status for the tutor, whatever the tab - shown on the face only.
  let tutorState = speakingNow ? 'speaking' : 'idle';
  if (tab === 'live' && inCall) tutorState = liveStateOf(live);
  if (tab === 'teach' && !speakingNow) {
    if (teach.phase === TEACH_PHASE.RETAKING) tutorState = 'retaking';
    else if (teach.busy) tutorState = 'thinking';
    else if (teach.session && !teach.passed && !teach.failed) tutorState = 'explain';
  }

  const stage = (
    <TutorStage
      state={tutorState}
      level={live.level}
      connected={avatarConnected}
      onConnect={() => setAvatarConnected(true)}
      onDisconnect={disconnectAvatar}
      onAvailabilityChange={setAvatarLive}
      controllerRef={avatarRef}
      avatarLine={voice.avatarLine}
      onAvatarLineEnd={voice.onAvatarLineEnd}
      muted={muted}
      onToggleMute={() => setMuted((m) => !m)}
      fill
    />
  );

  return (
    <div className="flex flex-col gap-5">
      {/* Title, context, then the three modes. */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-ink">Tutor</h1>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-3 text-sm text-muted">
            <span>Redwan knows your lessons, weak spots and past conversations.</span>
            {lesson && (
              <span className="inline-flex items-center gap-1 text-primary-300">
                <BookOpen className="h-3.5 w-3.5" />
                {lesson.title}
              </span>
            )}
          </p>
        </div>

        <div role="tablist" aria-label="Ways to learn with Redwan" className="flex w-full rounded-lg border border-line bg-surface p-1 lg:w-auto">
          {TABS.map(({ id, label, short, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => switchTab(id)}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded px-3.5 py-2 text-sm font-medium transition-colors lg:flex-none ${
                tab === id ? 'bg-primary-600 text-white' : 'text-muted hover:bg-raised hover:text-body'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span className="sm:hidden">{short}</span>
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Half the screen is Redwan's face; the other half is everything else
          for the current mode. The face stays mounted in every tab, so a
          video connection survives switching. */}
      <div className="grid grid-cols-1 gap-5 lg:h-[calc(100vh-12.5rem)] lg:min-h-[600px] lg:grid-cols-2">
        <div className="min-h-0">{stage}</div>

        <div className="flex min-h-0 flex-col gap-4">
          {tab === 'live' && inCall && <LiveControls live={live} bar />}
          {tab === 'teach' && <TeachChallenge teach={teach} compact />}
          {tab === 'chat' && (
            <div className="flex items-end gap-2">
              <Select
                label="Conversation"
                id="tutor-conversation"
                className="min-w-0 flex-1"
                value={selectedConvRef ? String(selectedConvRef) : ''}
                onChange={(e) => selectConversation(e.target.value || null)}
                disabled={loadingConversations}
              >
                <option value="">{conversations.length ? 'Start a new conversation' : 'No conversations yet'}</option>
                {conversations.map((conv) => (
                  <option key={conv.id} value={String(conv.number)}>{conv.title || 'Untitled'}</option>
                ))}
              </Select>
              <Button variant="secondary" onClick={() => newConversation().catch(() => {})} title="New conversation">
                <Plus className="h-4 w-4" />
                New
              </Button>
              {selectedConvRef && (
                <Button
                  variant="ghost"
                  onClick={(e) => removeConversation(e, selectedConvRef)}
                  title="Delete this conversation"
                  aria-label="Delete this conversation"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          )}

          <section className="flex min-h-[460px] flex-1 flex-col overflow-hidden rounded-lg border border-line bg-surface lg:min-h-0">
            {tab === 'live' && (
              <LivePanel
                live={live}
                conversationTitle={selectedConv?.title}
                lessonTitle={lesson?.title}
                avatarLive={avatarLive}
                onStart={startLive}
              />
            )}
            {tab === 'teach' && <TeachConversation teach={teach} />}
            {tab === 'chat' && (
              // Keyed by conversation so it reloads anything said in a live call.
              <ChatPanel
                key={selectedConvRef || 'new'}
                conversationId={selectedConvRef}
                onConversationCreated={(conv) => {
                  setConversations((prev) => [conv, ...prev]);
                  selectConversation(conv.number);
                }}
                onThinkingStart={voice.stop}
                onSpeakMessage={({ text }) => voice.speakText(text)}
                lessonId={lessonId}
                lessonTitle={lesson?.title}
              />
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
