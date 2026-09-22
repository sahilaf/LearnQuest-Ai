/**
 * TutorPage - OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
 * See plan.md §6.6, §6.7.
 *
 * Full-featured interactive AI Tutor dashboard:
 * - SyncTalk avatar that speaks each reply (or an offline panel when it cannot)
 * - Socratic conversation chat with markdown and code highlighting
 * - Conversation management (create, list, switch, delete)
 * - Dynamic lesson context attachment (when navigated from a lesson)
 * - Text-to-speech audio narration controls and mute toggles
 * - Responsive desktop split view and mobile-optimized layouts
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  Trash2,
  Volume2,
  VolumeX,
  Sparkles,
  Layers,
  History,
  Info,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  GraduationCap,
} from 'lucide-react';
import AvatarStage from '../../components/avatar/AvatarStage';
import TeachBackPanel from './TeachBackPanel';
import ChatPanel from '../../components/tutor/ChatPanel';
import PageHeader from '../../components/layout/PageHeader';
import { Button, Badge, Spinner } from '../../components/ui';
import {
  listConversations,
  deleteConversation,
  createConversation,
} from '../../api/tutor';
import { getLesson } from '../../api/lessons';

export default function TutorPage() {
  // The URL carries the conversation's per-user number (/tutor/7), not its
  // UUID. The API accepts either, so this value is passed straight through.
  const { conversationId: routeConvRef } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const lessonId = searchParams.get('lessonId') || searchParams.get('lesson_id');
  const [lessonData, setLessonData] = useState(null);

  // Conversations list state
  const [conversations, setConversations] = useState([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [selectedConvRef, setSelectedConvRef] = useState(routeConvRef || null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Avatar state machine
  const [avatarExpression, setAvatarExpression] = useState('neutral');
  const [spokenText, setSpokenText] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioMuted, setAudioMuted] = useState(false);

  // Active mobile view tab: 'split' (desktop default) | 'avatar' | 'chat'
  const [activeMobileTab, setActiveMobileTab] = useState('chat');

  // Right-hand column: ask Nova, or teach her. Teach-Back is the novel mode.
  const [rightMode, setRightMode] = useState('chat');

  // Sync route param with internal state
  useEffect(() => {
    if (routeConvRef) {
      setSelectedConvRef(routeConvRef);
    }
  }, [routeConvRef]);

  // Fetch optional attached lesson info
  useEffect(() => {
    if (!lessonId) {
      setLessonData(null);
      return;
    }
    getLesson(lessonId)
      .then((data) => setLessonData(data))
      .catch((err) => console.warn('Could not load lesson context:', err));
  }, [lessonId]);

  // Load user's conversations
  const fetchConversations = useCallback(async () => {
    try {
      setLoadingConversations(true);
      const res = await listConversations({ page: 1, page_size: 30 });
      const items = res?.items || (Array.isArray(res) ? res : []);
      setConversations(items);

      // If no conversation is active and conversations exist, select the latest
      if (!selectedConvRef && !routeConvRef && items.length > 0) {
        setSelectedConvRef(items[0].number);
        navigate(`/tutor/${items[0].number}`, { replace: true });
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setLoadingConversations(false);
    }
  }, [selectedConvRef, routeConvRef, navigate]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Handle new conversation creation
  const handleNewConversation = async () => {
    try {
      const title = lessonData
        ? `Discussion: ${lessonData.title?.slice(0, 24)}...`
        : 'New conversation';
      const created = await createConversation({
        title,
        lesson_id: lessonId || undefined,
      });

      setConversations((prev) => [created, ...prev]);
      setSelectedConvRef(created.number);
      navigate(`/tutor/${created.number}`);
      setSidebarOpen(false);
    } catch (err) {
      console.error('Failed to create new conversation:', err);
    }
  };

  // Handle conversation deletion
  const handleDeleteConversation = async (e, convRef) => {
    e.stopPropagation();
    if (!window.confirm('Delete this conversation history?')) return;

    try {
      await deleteConversation(convRef);
      // Compare as strings: the value from the URL is a string, the one on the
      // record is a number, and `===` between them is silently always false.
      const remaining = conversations.filter(
        (c) => String(c.number) !== String(convRef),
      );
      setConversations(remaining);

      if (String(selectedConvRef) === String(convRef)) {
        const nextRef = remaining.length > 0 ? remaining[0].number : null;
        setSelectedConvRef(nextRef);
        navigate(nextRef ? `/tutor/${nextRef}` : '/tutor');
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  // Switch conversation
  const handleSelectConversation = (convRef) => {
    setSelectedConvRef(convRef);
    navigate(`/tutor/${convRef}`);
    setSidebarOpen(false);
  };

  // Avatar speech & expression coordination callbacks
  const handleAssistantReply = ({ reply, expression, text }) => {
    setAvatarExpression(expression || 'explaining');
    setSpokenText(text || reply || '');
    setIsSpeaking(true);
  };

  const handleThinkingStart = () => {
    setAvatarExpression('thinking');
    setIsSpeaking(false);
    setSpokenText('');
  };

  const handleSpeakMessage = ({ text, expression }) => {
    setAvatarExpression(expression || 'explaining');
    setSpokenText(text);
    setIsSpeaking(true);
  };

  const handleSpeechEnd = () => {
    setIsSpeaking(false);
    setAvatarExpression('neutral');
  };

  // Teach-Back speaks through the same avatar. Nova is arguing from a false
  // belief here, so she is 'explaining' rather than 'encouraging'.
  const handleNovaSpeak = useCallback((text) => {
    if (!text) return;
    setAvatarExpression('explaining');
    setSpokenText(text);
    setIsSpeaking(true);
  }, []);

  return (
    <div className="flex flex-col gap-4">
      {/* Top Header */}
      <PageHeader
        title="AI Avatar Tutor"
        subtitle="Real-time multimodal learning with intelligent lipsync, Socratic dialogue, and tailored explanations."
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAudioMuted((prev) => !prev)}
              className="flex items-center gap-1.5"
              title={audioMuted ? 'Unmute tutor audio' : 'Mute tutor audio'}
            >
              {audioMuted ? (
                <>
                  <VolumeX className="h-4 w-4 text-hard-fg" />
                  <span className="text-xs">Unmute</span>
                </>
              ) : (
                <>
                  <Volume2 className="h-4 w-4 text-easy-fg" />
                  <span className="text-xs">Mute Voice</span>
                </>
              )}
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setSidebarOpen((prev) => !prev)}
              className="flex items-center gap-1.5 lg:hidden"
            >
              <History className="h-4 w-4" />
              <span className="text-xs">Chats</span>
            </Button>

            <Button
              size="sm"
              onClick={handleNewConversation}
              className="flex items-center gap-1.5"
            >
              <Plus className="h-4 w-4" />
              <span className="text-xs">New Chat</span>
            </Button>
          </div>
        }
      />

      {/* Mobile Tab Toggle (Avatar / Chat) */}
      <div className="flex rounded-xl bg-raised p-1 lg:hidden">
        <button
          type="button"
          onClick={() => setActiveMobileTab('chat')}
          className={`flex-1 rounded-lg py-1.5 text-xs font-medium transition-all ${
            activeMobileTab === 'chat'
              ? 'bg-surface text-primary-600 shadow-sm'
              : 'text-muted hover:text-ink'
          }`}
        >
          Chat Stream
        </button>
        <button
          type="button"
          onClick={() => setActiveMobileTab('avatar')}
          className={`flex-1 rounded-lg py-1.5 text-xs font-medium transition-all ${
            activeMobileTab === 'avatar'
              ? 'bg-surface text-primary-600 shadow-sm'
              : 'text-muted hover:text-ink'
          }`}
        >
          Avatar Stage
        </button>
      </div>

      {/* Main Workspace Grid */}
      {/* Fill the viewport rather than a hard-coded 720px: the shell above this
          row (app header + page header + main padding) measures ~15rem, so the
          workspace fits without the page itself scrolling. The min-h floor keeps
          it usable on short screens, where scrolling is the right fallback. */}
      <div className="relative grid grid-cols-1 gap-5 lg:grid-cols-12 lg:h-[calc(100vh-16rem)] lg:min-h-[560px]">
        {/* Collapsible Sidebar (Drawer on mobile, left rail on desktop) */}
        <aside
          className={`fixed inset-y-0 left-0 z-40 w-72 transform bg-surface p-4 shadow-xl transition-transform duration-200 ease-in-out lg:static lg:z-auto lg:w-auto lg:transform-none lg:col-span-3 lg:rounded-lg lg:border lg:border-line/80 lg:shadow-sm lg: ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          }`}
        >
          <div className="flex h-full flex-col">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                <MessageSquare className="h-4 w-4 text-primary-500" />
                <span>Conversations</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleNewConversation}
                className="h-8 w-8 p-0"
                title="Create new conversation"
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
              {loadingConversations && (
                <div className="flex h-32 items-center justify-center">
                  <Spinner size="sm" />
                </div>
              )}

              {!loadingConversations && conversations.length === 0 && (
                <div className="py-8 text-center text-xs text-muted">
                  No conversations yet. Start chatting below!
                </div>
              )}

              {!loadingConversations &&
                conversations.map((conv) => {
                  const isActive = String(conv.number) === String(selectedConvRef);
                  return (
                    <div
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.number)}
                      className={`group relative flex cursor-pointer items-center justify-between rounded-xl px-3 py-2.5 text-xs transition-all ${
                        isActive
                          ? 'bg-primary-50 font-medium text-primary-700'
                          : 'text-body hover:bg-raised'
                      }`}
                    >
                      <div className="min-w-0 flex-1 pr-2">
                        <p className="truncate">{conv.title || 'Untitled chat'}</p>
                        <span className="text-[10px] text-muted">
                          {new Date(conv.updated_at || conv.created_at).toLocaleDateString(
                            [],
                            { month: 'short', day: 'numeric' }
                          )}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={(e) => handleDeleteConversation(e, conv.number)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-muted hover:text-hard-fg transition-opacity"
                        title="Delete conversation"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  );
                })}
            </div>

            {/* Lesson Context Tag if active */}
            {lessonData && (
              <div className="mt-3 rounded-xl border border-primary-100 bg-primary-50/60 p-2.5 text-xs text-primary-800">
                <div className="flex items-center gap-1.5 font-medium">
                  <BookOpen className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{lessonData.title}</span>
                </div>
                <p className="mt-0.5 text-[11px] opacity-80">Linked course lesson</p>
              </div>
            )}
          </div>
        </aside>

        {/* Mobile backdrop for drawer */}
        {sidebarOpen && (
          <div
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-30 bg-canvas/40 backdrop-blur-xs lg:hidden"
          />
        )}

        {/* Center/Left: Avatar Stage */}
        <div
          className={`h-[620px] flex-col gap-3 lg:col-span-4 lg:h-full lg:flex ${
            activeMobileTab === 'avatar' ? 'flex' : 'hidden lg:flex'
          }`}
        >
          <div className="flex-1 flex flex-col rounded-lg border border-line/80 bg-surface shadow-sm overflow-hidden">
            {/* Stage header info */}
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5 text-xs">
              <div className="flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${
                    isSpeaking ? 'bg-easy animate-pulse' : 'bg-line-strong'
                  }`}
                />
                <span className="font-medium text-body">
                  Nova · Socratic Tutor
                </span>
              </div>
              <Badge tone={isSpeaking ? 'primary' : 'neutral'}>
                {isSpeaking ? 'Narrating' : 'Ready'}
              </Badge>
            </div>

            {/* Avatar visual canvas & lipsync */}
            {/* AvatarStage is aspect-square, so its height tracks its width.
                min-h-0 lets this row shrink inside the fixed-height column, and
                the max-w cap stops the square from outgrowing the space it has. */}
            <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden p-3 bg-gradient-to-b from-raised to-surface">
              <div className="w-full max-w-[320px]">
                <AvatarStage
                  spokenText={spokenText}
                  isSpeaking={isSpeaking}
                  onSpeechEnd={handleSpeechEnd}
                  audioMuted={audioMuted}
                  onToggleMute={() => setAudioMuted((prev) => !prev)}
                />
              </div>
            </div>

            {/* Avatar Persona Card */}
            <div className="border-t border-line bg-raised/50 p-3.5 text-xs">
              <div className="flex items-start gap-2">
                <Sparkles className="h-4 w-4 text-primary-500 mt-0.5 shrink-0" />
                <div>
                  <h4 className="font-semibold text-ink">
                    Socratic AI Guide
                  </h4>
                  <p className="mt-0.5 text-muted text-[11px] leading-relaxed">
                    Trained to unpack mental models, diagnose misunderstandings, and
                    guide you toward solutions through questioning.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: ask Nova, or teach her */}
        <div
          className={`lg:col-span-5 h-[620px] lg:h-full ${
            activeMobileTab === 'chat' ? 'flex' : 'hidden lg:flex'
          } flex-col gap-2`}
        >
          <div className="flex shrink-0 items-center gap-1 rounded-lg border border-line bg-surface p-1">
            <button
              type="button"
              onClick={() => setRightMode('chat')}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                rightMode === 'chat'
                  ? 'bg-primary-600 text-white'
                  : 'text-muted hover:text-body'
              }`}
            >
              <MessageSquare className="h-3.5 w-3.5" />
              Ask Nova
            </button>
            <button
              type="button"
              onClick={() => setRightMode('teachback')}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                rightMode === 'teachback'
                  ? 'bg-primary-600 text-white'
                  : 'text-muted hover:text-body'
              }`}
            >
              <GraduationCap className="h-3.5 w-3.5" />
              Teach Nova
            </button>
          </div>

          <div className="min-h-0 flex-1">
            {/* Both panels stay mounted: switching tabs must not throw away an
                in-progress Teach-Back session or an unsent chat draft. */}
            <div className={`h-full ${rightMode === 'chat' ? 'block' : 'hidden'}`}>
              <ChatPanel
                conversationId={selectedConvRef}
                onConversationCreated={(newConv) => {
                  setConversations((prev) => [newConv, ...prev]);
                  setSelectedConvRef(newConv.number);
                  navigate(`/tutor/${newConv.number}`, { replace: true });
                }}
                onAssistantReply={handleAssistantReply}
                onThinkingStart={handleThinkingStart}
                onSpeakMessage={handleSpeakMessage}
                lessonId={lessonId}
                lessonTitle={lessonData?.title}
              />
            </div>
            <div
              className={`h-full overflow-hidden rounded-lg border border-line bg-surface ${
                rightMode === 'teachback' ? 'block' : 'hidden'
              }`}
            >
              <TeachBackPanel onNovaSpeak={handleNovaSpeak} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
