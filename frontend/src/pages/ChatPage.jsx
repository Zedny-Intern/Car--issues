import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import Navbar from '../components/layout/Navbar';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import Card from '../components/ui/Card';
import apiClient from '../services/api';
import ThemeToggle from '../components/ui/ThemeToggle';

export default function ChatPage() {
    const [searchParams] = useSearchParams();
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const [loadingSession, setLoadingSession] = useState(false);
    const [uploadingDoc, setUploadingDoc] = useState(false);

    const messagesEndRef = useRef(null);
    const messagesContainerRef = useRef(null);
    const docInputRef = useRef(null);

    // Initial load: Check for existing active session or create new
    useEffect(() => {
        const complaintId = searchParams.get('complaint_id');
        if (!complaintId) return;

        const initSession = async () => {
            if (sessionId || loadingSession) return;
            setLoadingSession(true);

            try {
                // 1. Try to get existing active session
                const sessionsRes = await apiClient.getChatSessions({
                    complaint_id: complaintId,
                    is_active: true
                });

                if (sessionsRes.success && sessionsRes.data && sessionsRes.data.length > 0) {
                    // Restore existing session
                    const existingSession = sessionsRes.data[0];
                    setSessionId(existingSession.id);

                    // Load messages
                    if (existingSession.messages) {
                        setMessages(existingSession.messages);
                    } else {
                        // If messages not included in list, fetch details
                        const fullSession = await apiClient.getChatSession(existingSession.id);
                        if (fullSession.success) {
                            setMessages(fullSession.data.messages || []);
                        }
                    }
                } else {
                    // Create new session
                    const createRes = await apiClient.createChatSession(complaintId);
                    if (createRes.success && createRes.data) {
                        setSessionId(createRes.data.id);
                        setMessages([{
                            role: 'system',
                            message: 'Chat session created! You can now discuss your complaint with the AI mechanic.'
                        }]);
                    } else {
                        throw new Error('Failed to create session');
                    }
                }
            } catch (error) {
                console.error('Error initializing session:', error);
                setMessages([{
                    role: 'system',
                    message: 'Error starting chat session. Please refresh to try again.'
                }]);
            } finally {
                setLoadingSession(false);
            }
        };

        initSession();
    }, [searchParams, sessionId, loadingSession]);

    // Smart auto-scroll
    useEffect(() => {
        const container = messagesContainerRef.current;
        if (!container) return;

        const { scrollTop, scrollHeight, clientHeight } = container;
        const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;

        if (isNearBottom || messages.length <= 2) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages]);


    const handleDocumentUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const complaintId = searchParams.get('complaint_id');
        if (!complaintId) {
            alert("No complaint ID found.");
            return;
        }

        setUploadingDoc(true);
        // Add optimistic system message
        setMessages(prev => [...prev, {
            role: 'system',
            message: `Uploading and analyzing document: ${file.name}...`
        }]);

        try {
            const response = await apiClient.uploadComplaintDocument(complaintId, file);

            if (response.success) {
                setMessages(prev => {
                    // Remove "uploading" message and add success
                    const filtered = prev.filter(m => !m.message.includes('Uploading and analyzing'));
                    return [...filtered, {
                        role: 'system',
                        message: `✅ Document "${file.name}" uploaded and analyzed by RAG! You can now ask questions about it.`
                    }];
                });
            } else {
                setMessages(prev => [...prev, {
                    role: 'system',
                    message: `❌ Error analyzing document: ${response.message || 'Unknown error'}`
                }]);
            }
        } catch (error) {
            console.error(error);
            setMessages(prev => [...prev, {
                role: 'system',
                message: `❌ Error uploading document.`
            }]);
        } finally {
            setUploadingDoc(false);
            if (docInputRef.current) docInputRef.current.value = '';
        }
    };

    const clearChat = async () => {
        if (!sessionId || !window.confirm("Are you sure you want to clear the chat? This will close the current session.")) return;

        setLoading(true);
        try {
            await apiClient.closeChatSession(sessionId);
            setSessionId(null);
            setMessages([]);
            // Effect will trigger re-creation
            window.location.reload();
        } catch (error) {
            console.error("Error clearing chat:", error);
            alert("Failed to clear chat");
        } finally {
            setLoading(false);
        }
    };

    const sendMessage = async () => {
        if (!input.trim() || loading || uploadingDoc) return;

        const userMessage = {
            role: 'user',
            message: input
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setLoading(true);

        try {
            const response = await apiClient.sendChatMessage(
                sessionId,
                userMessage.message
            );

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let aiResponse = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                aiResponse += chunk;

                setMessages(prev => {
                    const updated = [...prev];
                    const lastMsg = updated[updated.length - 1];
                    if (lastMsg?.role === 'assistant') {
                        lastMsg.message = aiResponse;
                    } else {
                        updated.push({ role: 'assistant', message: aiResponse });
                    }
                    return updated;
                });
            }
        } catch (error) {
            console.error('Error:', error);
            setMessages(prev => [...prev, {
                role: 'system',
                message: 'Error: Could not get response'
            }]);
        }

        setLoading(false);
    };

    return (
        <div className="min-h-screen bg-page-bg">
            <div className="absolute inset-0">
                <div className="grid-pattern absolute inset-0 animate-grid-move"></div>
                <div className="absolute top-20 left-10 w-96 h-96 bg-primary/20 rounded-full blur-3xl animate-pulse"></div>
                <div className="absolute bottom-20 right-10 w-96 h-96 bg-secondary/20 rounded-full blur-3xl animate-pulse"
                    style={{ animationDelay: '1s' }}></div>
            </div>

            <Navbar />
            <ThemeToggle />

            <div className="relative z-10 max-w-5xl mx-auto px-4 py-8">
                <Card className="h-[80vh] md:h-[calc(100vh-10rem)] shadow-2xl border border-border-color/20 overflow-hidden">
                    <div className="flex flex-col h-full w-full relative z-10">
                        {/* Header */}
                        <div className="bg-card-bg/90 backdrop-blur-xl border-b border-white/10 pb-4 mb-4 flex-shrink-0 flex justify-between items-center px-6 pt-6 rounded-t-xl z-20 relative shadow-lg">
                            <div>
                                <h2 className="text-2xl font-heading font-bold text-white flex items-center gap-2">
                                    <span className="text-primary">💬</span>
                                    Chat with AI Mechanic
                                </h2>
                                <p className="text-gray-300 text-sm">Powered by Text RAG</p>
                            </div>
                            <Button variant="danger" size="sm" onClick={clearChat} disabled={loading || loadingSession}>
                                Clear Chat
                            </Button>
                        </div>

                        {/* Messages */}
                        <div
                            className="flex-1 overflow-y-auto overflow-x-hidden space-y-4 px-4 min-h-0 scrollbar-thin"
                            ref={messagesContainerRef}
                            style={{ scrollbarWidth: 'thin' }}
                        >
                            {messages.length === 0 ? (
                                <div className="flex items-center justify-center h-full">
                                    <div className="text-center space-y-4">
                                        <div className="w-20 h-20 mx-auto rounded-full bg-primary/10 flex items-center justify-center">
                                            <svg className="w-12 h-12 text-primary" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd" />
                                            </svg>
                                        </div>
                                        <div>
                                            <h3 className="text-xl font-semibold text-text-main">Start a conversation</h3>
                                            <p className="text-muted">Ask about your car issue or upload a document.</p>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                messages.map((msg, i) => (
                                    <div
                                        key={i}
                                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                    >
                                        <div
                                            className={`max-w-[85%] md:max-w-[70%] rounded-xl p-4 break-words overflow-hidden ${msg.role === 'user' ? 'bg-primary hover:bg-primary-hover text-text-main' : msg.role === 'assistant' ? 'bg-card-bg text-text-main border border-border-color/20' : 'bg-surface/50 text-muted text-center'}`}
                                        >
                                            <div className="text-xs font-semibold mb-1 opacity-70">
                                                {msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'AI Mechanic' : 'System'}
                                            </div>
                                            <div className="whitespace-pre-wrap break-words overflow-wrap-anywhere">{msg.message}</div>
                                        </div>
                                    </div>
                                ))
                            )}
                            {loading && (
                                <div className="flex justify-start">
                                    <div className="bg-card-bg/50 rounded-xl p-4 border border-border-color/20">
                                        <Spinner size="sm" text="AI is thinking..." />
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Bottom Section */}
                        <div className="flex-shrink-0 mt-4 space-y-2 px-4 pb-4">
                            <div className="flex gap-2 items-center">
                                {/* Hidden Inputs */}
                                <input
                                    type="file"
                                    ref={docInputRef}
                                    onChange={handleDocumentUpload}
                                    accept=".pdf,.txt,.doc,.docx"
                                    className="hidden"
                                />

                                {/* Attach Buttons */}
                                <div className="flex flex-col gap-1">
                                    <button
                                        onClick={() => docInputRef.current?.click()}
                                        className="p-3 rounded-lg bg-input-bg border-2 border-border-color/20
                              hover:border-primary transition-all text-primary"
                                        title="Upload Document (PDF)"
                                        disabled={loading || uploadingDoc}
                                    >
                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                                        </svg>
                                    </button>
                                </div>

                                {/* Text Input */}
                                <input
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                                    placeholder={uploadingDoc ? "Uploading document..." : "Type your message..."}
                                    disabled={loading || uploadingDoc}
                                    className="flex-1 px-4 py-3 h-[88px] rounded-lg bg-input-bg border-2 border-border-color/20
                           text-text-main placeholder-muted/50
                           focus:border-primary focus:outline-none transition-all"
                                />

                                {/* Send Button */}
                                <Button onClick={sendMessage} disabled={loading || uploadingDoc} className="h-[88px]">
                                    {loading || uploadingDoc ? <Spinner size="sm" /> : (
                                        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                                            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                                        </svg>
                                    )}
                                </Button>
                            </div>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
}

