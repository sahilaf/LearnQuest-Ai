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

import AvatarStage from '../../components/avatar/AvatarStage';
import ChatPanel from '../../components/tutor/ChatPanel';
import { Spinner } from '../../components/ui';
import { createConversation, deleteConversation, listConversations } from '../../api/tutor';
import { getLesson } from '../../api/lessons';
import LivePanel from './LivePanel';
import { LiveStatusChip, VoiceOrb, liveStateOf } from './LiveStatus';
import TeachBackPanel from './TeachBackPanel';
import useLiveConversation from './useLiveConversation';
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

  // Speak through the face only where the face is on screen.
  const voice = useTutorVoice({
    avatarRef,
    useAvatar: avatarLive && tab !== 'chat',
    muted,
  });
  const live = useLiveConversation({ voice });

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

  const showAvatar = tab !== 'chat';
  const inCall = tab === 'live' && (live.status === 'live' || live.status === 'connecting');
  const liveState = inCall ? liveStateOf(live) : null;

  return (
    <div className="flex flex-col gap-4">
      {/* Title, context and the three tabs - nothing else up here. */}
      <div className="flex flex-wrap items-end justify-between gap-3">
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

        <div role="tablist" className="flex w-full rounded-lg border border-line bg-surface p-1 sm:w-auto">
          {TABS.map(({ id, label, short, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => switchTab(id)}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded px-3.5 py-1.5 text-sm font-medium transition-colors sm:flex-none ${
                tab === id ? 'bg-primary-600 text-white' : 'text-muted hover:text-body'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span className="sm:hidden">{short}</span>
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:h-[calc(100vh-13rem)] lg:min-h-[560px] lg:grid-cols-12">
        {/* The face. Mounted on every tab so a connection survives switching,
            hidden on Chat where it is not used. */}
        <div className={`${showAvatar ? 'flex' : 'hidden'} flex-col items-center gap-3 lg:col-span-5`}>
          <div className="w-full max-w-[440px]">
            {/* A voice-only call still gets a presence that shows whose turn it is. */}
            {inCall && !avatarConnected && (
              <VoiceOrb state={liveState} level={live.level} onConnectAvatar={() => setAvatarConnected(true)} />
            )}
            <div className={inCall && !avatarConnected ? 'hidden' : ''}>
            <AvatarStage
              connected={avatarConnected}
              onConnect={() => setAvatarConnected(true)}
              onDisconnect={disconnectAvatar}
              onAvailabilityChange={setAvatarLive}
              controllerRef={avatarRef}
              spokenText={voice.avatarLine.text}
              isSpeaking={voice.avatarLine.speaking}
              onSpeechEnd={voice.onAvatarLineEnd}
              audioMuted={muted}
              onToggleMute={() => setMuted((m) => !m)}
              overlay={liveState ? <LiveStatusChip state={liveState} level={live.level} /> : null}
            />
            </div>
          </div>
        </div>

        {/* Chat: conversation list beside the chat. */}
        {tab === 'chat' && (
          <aside className="flex min-h-[200px] flex-col rounded-lg border border-line bg-surface p-3 lg:col-span-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-ink">Conversations</span>
              <button
                type="button"
                onClick={() => newConversation().catch(() => {})}
                className="rounded p-1.5 text-muted transition-colors hover:bg-raised hover:text-ink"
                title="New conversation"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
              {loadingConversations && <div className="flex justify-center py-6"><Spinner size="sm" /></div>}
              {!loadingConversations && conversations.length === 0 && (
                <p className="py-6 text-center text-xs text-muted">No conversations yet.</p>
              )}
              {conversations.map((conv) => {
                const active = String(conv.number) === String(selectedConvRef);
                return (
                  <div
                    key={conv.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => selectConversation(conv.number)}
                    onKeyDown={(e) => { if (e.key === 'Enter') selectConversation(conv.number); }}
                    className={`group flex cursor-pointer items-center justify-between rounded px-2.5 py-2 text-sm transition-colors ${
                      active ? 'bg-primary-500/15 text-ink' : 'text-body hover:bg-raised'
                    }`}
                  >
                    <span className="truncate pr-2">{conv.title || 'Untitled'}</span>
                    <button
                      type="button"
                      onClick={(e) => removeConversation(e, conv.number)}
                      className="p-1 text-faint opacity-0 transition-opacity hover:text-hard-fg group-hover:opacity-100"
                      title="Delete conversation"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          </aside>
        )}

        <div
          className={`flex min-h-[520px] flex-col overflow-hidden rounded-lg border border-line bg-surface ${
            tab === 'chat' ? 'lg:col-span-9' : 'lg:col-span-7'
          }`}
        >
          {tab === 'live' && (
            <LivePanel
              live={live}
              conversationTitle={selectedConv?.title}
              lessonTitle={lesson?.title}
              avatarLive={avatarLive}
              onStart={startLive}
            />
          )}

          {/* Kept mounted: switching tabs must not throw away a session. */}
          <div className={`${tab === 'teach' ? 'block' : 'hidden'} h-full overflow-y-auto`}>
            <TeachBackPanel onNovaSpeak={tab === 'teach' ? voice.speakText : null} initialTopic={topicParam} />
          </div>

          {tab === 'chat' && (
            // Remounted per visit so it reloads anything said in a live call.
            <ChatPanel
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
        </div>
      </div>
    </div>
  );
}
