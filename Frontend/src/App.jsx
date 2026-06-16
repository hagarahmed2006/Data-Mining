import { useState, useCallback, useEffect } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:5000";
const FEEDBACK_STORAGE_KEY = "tikiTechFeedback";

const normalizeQuery = (text) => text.trim().toLowerCase().replace(/\s+/g, " ");

const getStoredFeedback = () => {
  try {
    return JSON.parse(localStorage.getItem(FEEDBACK_STORAGE_KEY)) || {};
  } catch (error) {
    return {};
  }
};

const getFeedbackForQuery = (queryText) => {
  const storedFeedback = getStoredFeedback();
  return storedFeedback[queryText] || {};
};

const saveFeedbackForQuery = (queryText, queryFeedback) => {
  if (!queryText) return;
  const storedFeedback = getStoredFeedback();
  storedFeedback[queryText] = queryFeedback;
  localStorage.setItem(FEEDBACK_STORAGE_KEY, JSON.stringify(storedFeedback));
};

function App() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [results, setResults] = useState([]);
  const [count, setCount] = useState(0);
  const [shown, setShown] = useState(0);
  const [metrics, setMetrics] = useState({ precision: 0, recall: 0, f1_score: 0 });
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState({});
  const [feedbackMsg, setFeedbackMsg] = useState("");
  const [activeQueryKey, setActiveQueryKey] = useState("");
  const [displayLimit, setDisplayLimit] = useState(5);
  const [showSplash, setShowSplash] = useState(true);

  // إخفاء شاشة البداية بعد 2.5 ثانية
  useEffect(() => {
    const timer = setTimeout(() => setShowSplash(false), 2500);
    return () => clearTimeout(timer);
  }, []);

  const updateSearchData = (data) => {
    setResults(data.results || []);
    setCount(data.count || 0);
    setShown(data.shown || (data.results || []).length);
    setMetrics({
      precision: data.precision ?? 0,
      recall: data.recall ?? 0,
      f1_score: data.f1_score ?? 0,
    });
  };

  const handleSearch = async (overrideQuery = query) => {
    const searchQuery = overrideQuery.trim() ? overrideQuery : query;
    if (!searchQuery.trim()) return;

    const queryKey = normalizeQuery(searchQuery);
    const savedFeedback = getFeedbackForQuery(queryKey);
    const activeFeedback = Object.keys(feedback).length > 0 ? feedback : savedFeedback;

    setLoading(true);
    setSearched(true);
    setSuggestions([]);
    setFeedback(activeFeedback);
    setActiveQueryKey(queryKey);
    setFeedbackMsg("");
    setDisplayLimit(5);

    try {
      const hasFeedback = Object.keys(activeFeedback).length > 0;
      const response = hasFeedback
        ? await fetch(`${API_BASE}/feedback-search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: searchQuery, feedback: activeFeedback }),
          })
        : await fetch(`${API_BASE}/search?q=${encodeURIComponent(searchQuery)}`);

      const data = await response.json();
      updateSearchData(data);
      if (hasFeedback) setFeedbackMsg("Feedback applied to ranking");
    } catch (error) {
      console.error("Search error:", error);
      setResults([]);
      setCount(0);
      setShown(0);
      setMetrics({ precision: 0, recall: 0, f1_score: 0 });
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = async (e) => {
    const value = e.target.value;
    setQuery(value);
    setSearched(false);
    setResults([]);
    setCount(0);
    setShown(0);
    setMetrics({ precision: 0, recall: 0, f1_score: 0 });
    setFeedback({});
    setFeedbackMsg("");
    setActiveQueryKey("");
    setDisplayLimit(5);

    if (!value.trim()) {
      setSuggestions([]);
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/suggest?q=${encodeURIComponent(value)}`);
      const data = await response.json();
      setSuggestions(data.suggestions || []);
    } catch (error) {
      console.error("Suggestion error:", error);
      setSuggestions([]);
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setQuery(suggestion);
    setSuggestions([]);
    handleSearch(suggestion);
  };

  const handleFeedback = useCallback(
    async (docId, value) => {
      const queryKey = activeQueryKey || normalizeQuery(query);
      const updated = { ...feedback };
      if (updated[docId] === value) {
        delete updated[docId];
      } else {
        updated[docId] = value;
      }
      setFeedback(updated);
      saveFeedbackForQuery(queryKey, updated);
      setFeedbackMsg("Feedback saved");

      try {
        const response = await fetch(`${API_BASE}/feedback-search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, feedback: updated }),
        });
        const data = await response.json();
        updateSearchData(data);
      } catch (error) {
        console.error("Feedback error:", error);
      }
    },
    [activeQueryKey, query, feedback]
  );

  const feedbackCount = Object.keys(feedback).length;

  const handleSeeMore = () => {
    setDisplayLimit(results.length);
  };

  const displayedResults = results.slice(0, displayLimit);

  // ========== Splash Screen ==========
  if (showSplash) {
    return (
      <div className="splashScreen">
        <div className="splashContent">
          <h1 className="splashTitle">TikiTech</h1>
          <div className="splashSpinner">
            <div className="pulseCircle"></div>
            <div className="pulseCircle delay1"></div>
            <div className="pulseCircle delay2"></div>
          </div>
          <p className="splashSubtitle">Smart technology search</p>
        </div>
      </div>
    );
  }

  // ========== Main App ==========
  return (
    <div className="container">
      <div className="floating icon1">💻</div>
      <div className="floating icon2">📱</div>
      <div className="floating icon3">⚙️</div>
      <div className="floating icon4">💾</div>
      <div className="floating icon5">🖥️</div>
      <div className="floating icon6">🛰️</div>
      <div className="floating icon7">🔌</div>
      <div className="floating icon8">🔋</div>

      <h1 className="title">TikiTech</h1>
      <p className="subtitle">Smart technology search</p>

      <div className="searchArea">
        <div className="searchBox">
          <input
            type="text"
            placeholder="Ask Tiki..."
            value={query}
            onChange={handleInputChange}
            onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
          />
          <button onClick={() => handleSearch(query)} disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </button>
        </div>

        {suggestions.length > 0 && (
          <div className="suggestionsBox">
            {suggestions.map((s, index) => (
              <div key={index} className="suggestionItem" onClick={() => handleSuggestionClick(s)}>
                🔍 {s}
              </div>
            ))}
          </div>
        )}
      </div>

      {searched && feedbackCount > 0 && (
        <div className="feedbackBanner">
          Feedback active for this query: {feedbackCount} document(s)
        </div>
      )}

      {feedbackMsg && <p className="feedbackMsg">{feedbackMsg}</p>}

      {searched && (
        <p className="resultsCount">
          Results Found: <strong>{count}</strong>
          {shown > 0 && <> | Showing: <strong>{displayedResults.length}</strong> of {shown}</>}
        </p>
      )}

      {searched && (
        <div className="metricsCard">
          <h3>Evaluation</h3>
          <div className="metricsGrid">
            <div className="metricItem">
              <span className="metricLabel">Precision</span>
              <span className="metricValue">{metrics.precision}</span>
            </div>
            <div className="metricItem">
              <span className="metricLabel">Recall</span>
              <span className="metricValue">{metrics.recall}</span>
            </div>
            <div className="metricItem">
              <span className="metricLabel">F1 Score</span>
              <span className="metricValue">{metrics.f1_score}</span>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loadingBox">
          <div className="spinner"></div>
          <p>Searching your technology dataset...</p>
        </div>
      ) : results.length === 0 && searched ? (
        <div className="noResults">
          <h3>🔍 No results found</h3>
        </div>
      ) : (
        searched && (
          <div className="results">
            {displayedResults.map((item) => {
              const fb = feedback[item.id];
              return (
                <div key={item.id} className="card">
                  <div className="cardTop">
                    <h3>{item.topic}</h3>
                    <span className="docIndex">Doc #{item.id}</span>
                  </div>

                  {/* صور فوق النص */}
                  {item.images && item.images.length > 0 && (
                    <div className="imageRow">
                      {item.images.slice(0, 3).map((url, idx) => (
                        <img
                          key={idx}
                          src={url}
                          alt={item.topic}
                          className="resultImg"
                          onError={(e) => { e.target.style.display = "none"; }}
                        />
                      ))}
                    </div>
                  )}

                  <p><strong>Category:</strong> {item.category}</p>
                  {item.source && <p><strong>Source:</strong> {item.source}</p>}

                  <div className="scoreRow">
                    {item.hybrid_score !== undefined && (
                      <span className="scoreBadge hybridBadge">Hybrid: {item.hybrid_score}</span>
                    )}
                    {item.bm25_score !== undefined && (
                      <span className="scoreBadge bm25Badge">BM25: {item.bm25_score}</span>
                    )}
                    {item.bert_score !== undefined && (
                      <span className="scoreBadge bertBadge">BERT: {item.bert_score}</span>
                    )}
                  </div>

                  <p className="summaryText">{item.summary}</p>

                  <div className="cardFooter">
                    {item.page_url && (
                      <a href={item.page_url} target="_blank" rel="noreferrer" className="sourceLink">
                        View Source
                      </a>
                    )}
                    <div className="feedbackBtns">
                      <button
                        className={`fbBtn relevantBtn ${fb === "relevant" ? "active" : ""}`}
                        onClick={() => handleFeedback(item.id, "relevant")}
                        title="Mark as relevant"
                      >
                        👍
                      </button>
                      <button
                        className={`fbBtn irrelevantBtn ${fb === "irrelevant" ? "active" : ""}`}
                        onClick={() => handleFeedback(item.id, "irrelevant")}
                        title="Mark as irrelevant"
                      >
                        👎
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}

            {results.length > displayLimit && (
              <div className="seeMoreContainer">
                <button className="seeMoreBtn" onClick={handleSeeMore}>
                  See More ({results.length - displayLimit} remaining)
                </button>
              </div>
            )}
          </div>
        )
      )}
    </div>
  );
}

export default App;