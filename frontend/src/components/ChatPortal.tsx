import React, { useState, useEffect, useRef } from 'react';
import { sendChatMessage, fetchDatasetCatalog } from '../api';
import type { ChatMessageItem } from '../types';

interface ChatPortalProps {
  onSwitchToAdmin: () => void;
  backendConnected: boolean;
}

export default function ChatPortal({ onSwitchToAdmin, backendConnected }: ChatPortalProps) {
  const [activeDataset, setActiveDataset] = useState<string>('lumen');
  const [companyName, setCompanyName] = useState<string>('Lumen Analytics');
  const [companyDomain, setCompanyDomain] = useState<string>('Product Analytics & B2B SaaS');
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchDatasetCatalog()
      .then((data) => {
        setActiveDataset(data.active_dataset);
        const activeEntry = data.catalog.find((c: any) => c.id === data.active_dataset);
        const cName = activeEntry ? activeEntry.name : 'Company';
        const cDom = activeEntry ? activeEntry.domain : '';
        setCompanyName(cName);
        setCompanyDomain(cDom);

        setMessages([
          {
            id: 'welcome',
            role: 'assistant',
            content: `Hello! I am your AI Knowledge Ambassador for ${cName}. I can answer questions about our product plans, pricing tiers, specifications, and policies—all grounded directly in our live company database.\n\nHow can I help you today?`,
            citations: data.active_dataset === 'cloudgrid' ? ['doc:gpu_pricing_sheet', 'doc:cloud_faq'] : ['doc:pricing_page', 'doc:faq'],
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      })
      .catch(() => {
        setMessages([
          {
            id: 'welcome',
            role: 'assistant',
            content:
              "Hello! I am your AI Knowledge Ambassador. I can answer questions about our product features, pricing tiers, platform capabilities, and policies—all grounded directly in our live company database.\n\nHow can I help you today?",
            citations: ['doc:pricing_page', 'doc:faq'],
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function handleSend(textToSend?: string) {
    const text = textToSend || input;
    if (!text.trim() || loading) return;

    const userMsg: ChatMessageItem = {
      id: `u_${Date.now()}`,
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput('');
    setLoading(true);

    try {
      const apiPayload = newHistory
        .filter((m) => m.id !== 'welcome')
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await sendChatMessage(apiPayload);
      const botMsg: ChatMessageItem = {
        id: `b_${Date.now()}`,
        role: 'assistant',
        content: res.content,
        citations: res.citations,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessageItem = {
        id: `err_${Date.now()}`,
        role: 'assistant',
        content: `Sorry, I encountered an issue connecting to the company brain: ${err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="chat-portal-container">
      {/* Top Header */}
      <header className="chat-navbar">
        <div className="brand">
          <div className="brand-icon">TB</div>
          <div>
            <div className="brand-title">{companyName} AI Assistant</div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>
              {companyDomain ? `${companyDomain} \u2022 ` : ''}Grounded in <code>kb_main</code>
            </div>
          </div>
          <span className="status-pill status-CHECKS_PASSED" style={{ fontSize: '10px' }}>
            {backendConnected ? 'Database: Active' : 'Connecting...'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button className="btn btn-primary" onClick={onSwitchToAdmin}>
            TruthBranch Admin Console &rarr;
          </button>
        </div>
      </header>

      {/* Main Chat Flow */}
      <div className="chat-body">
        <div className="chat-messages-scroll">
          {/* Prompt Starters */}
          <div className="prompt-starters">
            <div className="starters-label">Try asking:</div>
            <div className="starters-pills">
              {activeDataset === 'cloudgrid' ? (
                <>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('How much does an H100 GPU instance cost?')}
                  >
                    💡 How much does an H100 cost?
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('What is your uptime SLA guarantee?')}
                  >
                    💡 What is your uptime SLA guarantee?
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('Tell me about annual reserved GPU clusters.')}
                  >
                    💡 Tell me about reserved clusters
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('Who can I contact for capacity reservations?')}
                  >
                    💡 Who can I contact for support?
                  </button>
                </>
              ) : activeDataset === 'meridian' ? (
                <>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('What is your refund policy?')}
                  >
                    💡 What is your refund policy?
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('How much does the Business plan cost?')}
                  >
                    💡 How much does the Business plan cost?
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('What is the PTO vacation days policy?')}
                  >
                    💡 What is the HR PTO policy?
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('What is your SLA uptime guarantee?')}
                  >
                    💡 What is your SLA uptime guarantee?
                  </button>
                </>
              ) : (
                <>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('How much does the Pro plan cost?')}
                  >
                    💡 How much does the Pro plan cost?
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('What is your refund policy?')}
                  >
                    💡 What is your refund policy?
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('Tell me about your enterprise analytics features.')}
                  >
                    💡 Tell me about enterprise features
                  </button>
                  <button
                    className="starter-btn"
                    onClick={() => handleSend('Who can I contact for support upgrades?')}
                  >
                    💡 Who can I contact for support?
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Messages */}
          {messages.map((m) => (
            <div key={m.id} className={`message-row ${m.role}`}>
              <div className="message-bubble">
                <div className="message-header">
                  <span className="message-author">
                    {m.role === 'user' ? 'You' : `${companyName} Ambassador`}
                  </span>
                  <span className="message-time">{m.timestamp}</span>
                </div>
                <div className="message-text">{m.content}</div>

                {m.citations && m.citations.length > 0 && (
                  <div className="message-citations">
                    <span className="citations-label">Sources cited:</span>
                    {m.citations.map((c) => (
                      <span key={c} className="path-node">
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row assistant">
              <div className="message-bubble loading">
                <div className="typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                  Consulting authoritative knowledge base (kb_main)...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="chat-input-wrapper">
          <div className="chat-input-box">
            <input
              className="chat-text-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about pricing, plans, features, or policies..."
              disabled={loading}
              autoFocus
            />
            <button
              className="btn btn-primary"
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
            >
              Send &rarr;
            </button>
          </div>
          <div className="chat-footer-note">
            ⚡ <b>Live Truth Branching:</b> When you propose and merge a price change in the{' '}
            <span
              style={{ color: '#818cf8', cursor: 'pointer', textDecoration: 'underline' }}
              onClick={onSwitchToAdmin}
            >
              Admin Console
            </span>
            , ask the price again to watch live truth propagation in real time!
          </div>
        </div>
      </div>
    </div>
  );
}
