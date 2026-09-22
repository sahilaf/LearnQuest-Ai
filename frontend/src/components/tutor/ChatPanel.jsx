/**
 * ChatPanel - OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
 * See plan.md §6.3, §6.7.
 *
 * Provides the interactive AI conversation interface:
 * - Real-time message streaming / sending
 * - Rich Markdown formatting with code block styling
 * - Suggested prompt chips for guided learning
 * - Web Speech API Speech-to-Text voice input
 * - Direct sync with AvatarStage (speaking & expressions)
 * - Message replay & audio narration controls
 */
import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Send,
  Mic,
  MicOff,
  Volume2,
  Copy,
  Check,
  Sparkles,
  Bot,
  User,
  AlertCircle,
  HelpCircle,
  Code,
  BookOpen,
  Lightbulb,
} from 'lucide-react';
import {
  createConversation,
  listMessages,
  sendMessage,
} from '../../api/tutor';
import { Button, Spinner } from '../ui';

// Quick starter prompt suggestions
const QUICK_PROMPTS = [
  {
    icon: Lightbulb,
    label: 'Explain simply',
    prompt: 'Can you explain the core idea here in simple terms with an analogy?',
  },
  {
    icon: Code,
    label: 'Real-world example',
    prompt: 'Give me a concrete, real-world example of how this is applied.',
  },
  {
    icon: HelpCircle,
    label: 'Quiz my knowledge',
    prompt: 'Ask me a quick question to test if I truly understand this concept.',
  },
  {
    icon: BookOpen,
    label: 'Common mistakes',
    prompt: 'What are the most common misconceptions or mistakes learners make with this?',
  },
];

/**
 * Strips markdown symbols and code fences for natural speech synthesis.
 */
function cleanTextForSpeech(text) {
  if (!text) return '';
  return text
    .replace(/```[\s\S]*?```/g, 'Code example omitted.')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[#*_~>]/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .trim();
}

export default function ChatPanel({
  conversationId = null,
  onConversationCreated = null,
  onAssistantReply = null,
  onThinkingStart = null,
  onSpeakMessage = null,
  lessonId = null,
  lessonTitle = null,
}) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const recognitionRef = useRef(null);

  // Auto-scroll to bottom whenever messages update or loading changes
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, submitting]);

  // Load message history when conversationId changes
  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    listMessages(conversationId)
      .then((data) => {
        if (isMounted) {
          const list = Array.isArray(data) ? data : data?.messages || [];
          setMessages(list);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err?.detail || 'Failed to load message history.');
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [conversationId]);

  // Initialize Web Speech Recognition if available
  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          setInputValue((prev) => (prev ? `${prev} ${transcript}` : transcript));
        }
        setIsRecording(false);
      };

      recognition.onerror = () => {
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  const toggleRecording = () => {
    if (!recognitionRef.current) {
      alert('Speech recognition is not supported in this browser.');
      return;
    }

    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsRecording(true);
      } catch (err) {
        console.error('Speech recognition start failed:', err);
      }
    }
  };

  const handleCopy = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSend = async (textToSend = null) => {
    const content = (textToSend || inputValue).trim();
    if (!content || submitting) return;

    setError(null);
    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Inform avatar that tutor is formulating an answer
    onThinkingStart?.();

    let activeConvId = conversationId;

    // Optimistically add user message
    const tempUserMsg = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setSubmitting(true);

    try {
      // Auto-create conversation if none exists yet
      if (!activeConvId) {
        const titleSnippet = content.slice(0, 36) + (content.length > 36 ? '...' : '');
        const newConv = await createConversation({
          title: titleSnippet,
          lesson_id: lessonId || undefined,
        });
        activeConvId = newConv.id;
        onConversationCreated?.(newConv);
      }

      // Send message to backend
      const response = await sendMessage(activeConvId, content);

      const assistantMsg = {
        id: response.message_id || `msg-${Date.now()}`,
        role: 'assistant',
        content: response.reply,
        created_at: new Date().toISOString(),
        expression: response.expression || 'explaining',
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // Trigger Avatar Stage speech & mouth animation
      onAssistantReply?.({
        reply: response.reply,
        expression: response.expression || 'explaining',
        text: cleanTextForSpeech(response.reply),
      });
    } catch (err) {
      setError(err?.detail || 'Failed to get a response from the AI tutor.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaInput = (e) => {
    setInputValue(e.target.value);
    // Auto-grow textarea up to 140px
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-line/80 bg-surface/95 shadow-sm backdrop-blur-sm">
      {/* Context banner if tied to a lesson */}
      {lessonTitle && (
        <div className="flex items-center gap-2 border-b border-line bg-primary-50/50 px-4 py-2 text-xs font-medium text-primary-700">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Active Context: {lessonTitle}</span>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {loading && (
          <div className="flex h-40 flex-col items-center justify-center gap-2 text-muted">
            <Spinner size="md" />
            <p className="text-xs">Loading conversation history...</p>
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div className="my-auto flex flex-col items-center justify-center py-8 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-lg bg-gradient-to-tr from-primary-500 to-primary-600 text-white shadow-md shadow-primary-500/20">
              <Bot className="h-7 w-7" />
            </div>
            <h3 className="text-lg font-semibold text-ink">
              Meet Your AI Socratic Tutor
            </h3>
            <p className="mt-1.5 max-w-sm text-sm text-muted">
              Ask anything about your courses, request step-by-step breakdowns, or
              test your conceptual mastery with interactive guidance.
            </p>

            {/* Quick Prompt Chips */}
            <div className="mt-6 grid w-full max-w-md grid-cols-1 gap-2.5 sm:grid-cols-2">
              {QUICK_PROMPTS.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => handleSend(item.prompt)}
                    className="flex items-start gap-2.5 rounded-xl border border-line/80 bg-raised/80 p-3 text-left transition-all hover:border-primary-400 hover:bg-primary-50/50 hover:shadow-sm"
                  >
                    <div className="rounded-lg bg-primary-100 p-1.5 text-primary-600">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-ink">
                        {item.label}
                      </div>
                      <div className="mt-0.5 text-[11px] leading-tight text-muted">
                        {item.prompt.slice(0, 42)}...
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Rendered Messages */}
        {messages.map((msg, idx) => {
          const isUser = msg.role === 'user';
          const isCopied = copiedId === msg.id;

          return (
            <div
              key={msg.id || idx}
              className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
            >
              {/* Avatar Icon */}
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-medium shadow-sm ${
                  isUser
                    ? 'bg-primary-600 text-white'
                    : 'bg-gradient-to-tr from-surface to-primary-600 text-primary-300 ring-2 ring-primary-500/20'
                }`}
              >
                {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>

              {/* Message Bubble */}
              <div
                className={`group relative max-w-[85%] rounded-lg px-4 py-3 text-sm shadow-sm transition-all sm:max-w-[78%] ${
                  isUser
                    ? 'rounded-tr-xs bg-gradient-to-r from-primary-600 to-primary-600 text-white'
                    : 'rounded-tl-xs border border-line/80 bg-surface text-ink'
                }`}
              >
                {isUser ? (
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                ) : (
                  <div className="prose prose-sm max-w-none space-y-2 leading-relaxed break-words">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({ node, inline, className, children, ...props }) {
                          return inline ? (
                            <code
                              className="rounded bg-raised px-1.5 py-0.5 font-mono text-xs text-primary-600"
                              {...props}
                            >
                              {children}
                            </code>
                          ) : (
                            <pre className="overflow-x-auto rounded-xl bg-canvas p-3 font-mono text-xs text-ink">
                              <code {...props}>{children}</code>
                            </pre>
                          );
                        },
                        p({ children }) {
                          return <p className="mb-2 last:mb-0">{children}</p>;
                        },
                        ul({ children }) {
                          return <ul className="list-disc pl-4 space-y-1 mb-2">{children}</ul>;
                        },
                        ol({ children }) {
                          return <ol className="list-decimal pl-4 space-y-1 mb-2">{children}</ol>;
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}

                {/* Bottom toolbar for assistant responses */}
                {!isUser && (
                  <div className="mt-2.5 flex items-center justify-between border-t border-line pt-2 text-xs text-muted">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() =>
                          onSpeakMessage?.({
                            text: cleanTextForSpeech(msg.content),
                            expression: 'explaining',
                          })
                        }
                        className="flex items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-raised hover:text-body"
                        title="Play explanation with Avatar voice"
                      >
                        <Volume2 className="h-3.5 w-3.5" />
                        <span className="text-[11px]">Listen</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleCopy(msg.id, msg.content)}
                        className="flex items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-raised hover:text-body"
                        title="Copy response"
                      >
                        {isCopied ? (
                          <>
                            <Check className="h-3.5 w-3.5 text-easy-fg" />
                            <span className="text-[11px] text-easy-fg">Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            <span className="text-[11px]">Copy</span>
                          </>
                        )}
                      </button>
                    </div>

                    <span className="text-[10px] opacity-70">
                      {new Date(msg.created_at || Date.now()).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Submitting / Thinking Indicator */}
        {submitting && (
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-surface to-primary-600 text-primary-300 ring-2 ring-primary-500/20">
              <Bot className="h-4 w-4 animate-pulse" />
            </div>
            <div className="rounded-lg rounded-tl-xs border border-line/80 bg-surface px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2 text-xs text-muted">
                <span className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary-500 [animation-delay:-0.3s]"></span>
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary-500 [animation-delay:-0.15s]"></span>
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary-500"></span>
                </span>
                <span>Tutor is formulating an answer...</span>
              </div>
            </div>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-hard/30 bg-hard-bg p-3 text-xs text-hard-fg">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="flex-1">{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="font-medium underline hover:text-hard-fg"
            >
              Dismiss
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Message Input Bar */}
      <div className="border-t border-line/80 bg-raised/50 p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="relative flex items-end gap-2 rounded-xl border border-line bg-surface p-1.5 shadow-sm transition-focus focus-within:border-primary-500 focus-within:ring-2 focus-within:ring-primary-500/20"
        >
          {/* Speech-to-text mic button */}
          <button
            type="button"
            onClick={toggleRecording}
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors ${
              isRecording
                ? 'bg-hard text-white animate-pulse'
                : 'text-muted hover:bg-raised hover:text-body'
            }`}
            title={isRecording ? 'Stop listening' : 'Speak your question (Voice Input)'}
          >
            {isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          </button>

          {/* Text Area */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={inputValue}
            onChange={handleTextareaInput}
            onKeyDown={handleKeyDown}
            placeholder={
              isRecording ? 'Listening to your voice...' : 'Ask your tutor a question... (Enter to send)'
            }
            className="max-h-36 min-h-[36px] flex-1 resize-none bg-transparent py-1.5 text-sm text-ink outline-none placeholder:text-muted"
          />

          {/* Send Button */}
          <Button
            type="submit"
            size="sm"
            disabled={!inputValue.trim() || submitting}
            className="h-9 shrink-0 px-3.5"
          >
            {submitting ? <Spinner size="sm" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>

        <div className="mt-1.5 flex items-center justify-between px-1 text-[11px] text-muted">
          <span>Shift + Enter for new line</span>
          <span>Socratic AI Mode · Active</span>
        </div>
      </div>
    </div>
  );
}
