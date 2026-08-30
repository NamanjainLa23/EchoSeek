import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactPlayer from "react-player";
import { X, Mic, Pause, Play, Home, Search, Tv, Film, AppWindow, Volume2, VolumeX, Maximize, Minimize } from "lucide-react";
import { forwardRef, useImperativeHandle } from 'react';

const EASE = [0.16, 1, 0.3, 1];
const RADIUS = 22;

const HERO = {
  title: "TYLER PERRY'S THE OVAL",
  synopsis:
    "A seemingly perfect interracial first family becomes the White House's newest residents. Behind closed doors they unleash a torrent of corruption.",
  poster:
    "https://images.unsplash.com/photo-1520813792240-56fc4a3765a7?q=80&w=2400&auto=format&fit=crop",
  cta: "Watch Now",
  videoUrl: "https://www.youtube.com/watch?v=CICbN1lKjxk",
  tint: "#02b3ff",
};

const VIDEO_ID_MAP = {
  //"D2krcvO3z1A": "https://www.youtube.com/watch?v=D2krcvO3z1A",
  "ZTqOTb-lT-k": "https://www.youtube.com/watch?v=ZTqOTb-lT-k",
  "cn9zxlfDPDQ": "https://www.youtube.com/watch?v=cn9zxlfDPDQ",
  "LXb3EKWsInQ": "https://www.youtube.com/watch?v=LXb3EKWsInQ",
};

const ROWS = [
  {
    id: "row0",
    title: "AI-Controlled Videos",
    items: [
      {
        id: "ai-vid-1",
        title: "",
        thumb:
          "https://img.youtube.com/vi/ZTqOTb-lT-k/hqdefault.jpg",
        playable: true,
        videoUrl: "https://www.youtube.com/watch?v=ZTqOTb-lT-k",
      },
      {
        id: "ai-vid-2",
        title: "",
        thumb:
          "https://img.youtube.com/vi/_0Ecqv3qPUw/hqdefault.jpg",
        playable: true,
        videoUrl: "https://www.youtube.com/watch?v=cn9zxlfDPDQ",
      },
    ],
  },
  {
    id: "row2",
    title: "Continue Watching",
    items: [
      {
        id: "cw-1",
        title: "The Repair Shop on the Road",
        thumb:
          "https://images.unsplash.com/photo-1505685296765-3a2736de412f?q=80&w=1600&auto=format&fit=crop",
        playable: true,
        videoUrl: "https://www.youtube.com/watch?v=LXb3EKWsInQ",
        progress: 0.35,
      },
    ],
  },
  {
    id: "row1",
    title: "Live TV on Freely",
    items: [
      {
        id: "playable-1",
        title: "The Repair Shop on the Road",
        thumb:
          "https://images.unsplash.com/photo-1505685296765-3a2736de412f?q=80&w=1600&auto=format&fit=crop",
        playable: true,
        videoUrl: "https://www.youtube.com/watch?v=cn9zxlfDPDQ",
      },
      { id: "soon-1", title: "Earth's Greatest Spectacles", thumb: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?q=80&w=1600&auto=format&fit=crop", playable: false },
      { id: "soon-2", title: "Tipping Point", thumb: "https://images.unsplash.com/photo-1546500840-ae38253aba9b?q=80&w=1600&auto=format&fit=crop", playable: false },
      { id: "soon-3", title: "A New Life in the Sun", thumb: "https://images.unsplash.com/photo-1469474968028-56623f02e42e?q=80&w=1600&auto=format&fit=crop", playable: false },
      { id: "soon-4", title: "Bargain-Loving Brits in the Sun", thumb: "https://images.unsplash.com/photo-1485841890310-6a055c88698a?q=80&w=1600&auto=format&fit=crop", playable: false },
      { id: "soon-5", title: "Gilmore Girls", thumb: "https://images.unsplash.com/photo-1513475382585-d06e58bcb0ea?q=80&w=1600&auto=format&fit=crop", playable: false },
    ],
  },
];

const useSpeech = (videoId, setSearchQuery, pauseVideo, setPlayerUrl, setCurrentVideoId, setSeekTime) => {
  const [listening, setListening] = useState(false);
  const recRef = useRef(null);
  const [transcript, setTranscript] = useState("");

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;

    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";

    rec.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }

      const result = final || interim;
      setTranscript(result);
      setSearchQuery(result);
      console.log("Speech:", result);

      // Send to backend or AWS Transcribe
      if (final) {
        fetch("http://localhost:8000/api/process_voice", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            transcript: final,
            //video_id: videoId || "D2krcvO3z1A"
            video_id: videoId || "ZTqOTb-lT-k"
          }),
        })
          .then((res) => res.json())
          .then((data) => {console.log("Backend response:", data);
          if (data.status === "success" && data.timestamp && data.video_id) {
            // Send video_id and timestamp to frontend player
            const url = VIDEO_ID_MAP[data.video_id];
            if (url){
              setPlayerUrl(url);
              setCurrentVideoId(data.video_id);
              setSeekTime(null);
              setTimeout(() => {
                setSeekTime(data.timestamp);
              }, 300);
            }
          }
        })
          .catch((err) => console.error("Error:", err));
      }
    };

    rec.onend = () => setListening(false);
    recRef.current = rec;
  }, []);
  const start = () => {
    try { 
      pauseVideo?.();  // Pause video if playing
      recRef.current?.start(); 
    } catch {}
    setListening(true);
  };
  const stop = () => { try { recRef.current?.stop(); } catch {} setListening(false); };
  return { listening, start, stop };
};

function TopBanner() {
  return (
    <div className="flex items-center justify-between mb-5 relative z-10 px-6">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-white/10" />
        <div className="text-white text-lg font-semibold tracking-tight">TiVo TV</div>
      </div>
      <div className="text-white/70 text-sm">Powered by TiVo</div>
    </div>
  );
}

function LeftNavBar({ micListening, onMicDown, onMicUp }) {
  const items = [
    { label: "Home", icon: Home },
    { label: "Search", icon: Search },
    { label: "Live", icon: Tv },
    { label: "Shows", icon: Film },
    { label: "Apps", icon: AppWindow },
  ];
  const selected = 0;

  return (
    <nav className="fixed left-0 top-0 h-full w-[96px] bg-black z-50">
      <div className="relative h-full">
        <ul className="pt-8 flex flex-col items-center gap-9">
          {items.map(({ label, icon: Icon }, i) => (
            <li key={label}>
              <button
                aria-label={label}
                className="relative text-white/85 hover:text-white transition-transform hover:scale-110 focus:scale-110 outline-none"
                style={{ lineHeight: 0 }}
              >
                {i === selected && (
                  <span className="absolute -inset-3 rounded-full blur-md opacity-90" style={{ background: "radial-gradient(closest-side, rgba(0,225,255,.5), transparent)" }} />
                )}
                <Icon size={22} className={i === selected ? "text-white drop-shadow-[0_0_14px_rgba(0,225,255,.9)]" : ""} />
              </button>
            </li>
          ))}
        </ul>

        <div className="absolute left-1/2 -translate-x-1/2 top-[55vh]">
          <button
            onMouseDown={onMicDown}
            onMouseUp={onMicUp}
            onTouchStart={onMicDown}
            onTouchEnd={onMicUp}
            aria-label="Voice"
            className="relative w-10 h-10 rounded-full flex items-center justify-center"
          >
            <span className="absolute -inset-[7px] rounded-full blur-[8px] opacity-95 animate-spin-slow" style={{ background: "conic-gradient(from 0deg,#00e5ff,#7b5cff,#00e5ff)" }} />
            <span className="absolute -inset-2 rounded-full blur-md opacity-50" style={{ background: "radial-gradient(circle, rgba(0,229,255,.45), rgba(123,92,255,.35) 60%, transparent 70%)" }} />
            <span className="absolute inset-0 rounded-full bg-[#1b1f26] shadow-[inset_0_0_0_2px_rgba(255,255,255,.08)]" />
            <Mic className="relative text-white" size={16} />
            {micListening && (
              <motion.span
                className="absolute inset-0 rounded-full"
                initial={{ boxShadow: "0 0 0 0 rgba(0,229,255,.5)" }}
                animate={{ boxShadow: ["0 0 0 0 rgba(0,229,255,.55)", "0 0 0 12px rgba(0,229,255,0)"] }}
                transition={{ duration: 1, repeat: Infinity, ease: "easeOut" }}
              />
            )}
          </button>
        </div>
      </div>
    </nav>
  );
}

function FloatingMic({ micListening, onMicDown, onMicUp }) {
  return (
    <div className="relative z-50">
      <button
        onMouseDown={onMicDown}
        onMouseUp={onMicUp}
        onTouchStart={onMicDown}
        onTouchEnd={onMicUp}
        className="relative w-10 h-10 rounded-full flex items-center justify-center bg-black/70"
      >
        <Mic className="text-white" size={16} />
        {micListening && (
          <motion.span
            className="absolute inset-0 rounded-full"
            initial={{ boxShadow: "0 0 0 0 rgba(0,229,255,.5)" }}
            animate={{ boxShadow: ["0 0 0 0 rgba(0,229,255,.55)", "0 0 0 12px rgba(0,229,255,0)"] }}
            transition={{ duration: 1, repeat: Infinity, ease: "easeOut" }}
          />
        )}
      </button>
    </div>
  );
}

function Hero({ onWatch }) {
  return (
    <div className="relative w-full h-[56vh] min-h-[420px] overflow-hidden">
      <img src={HERO.poster} alt={HERO.title} className="object-cover w-full h-full absolute inset-0" />
      <div
        className="absolute inset-0"
        style={{
          background:
            `linear-gradient(180deg, rgba(6,8,11,.95) 0%, rgba(10,13,18,.85) 40%, rgba(12,16,22,.65) 70%, rgba(11,14,19,1) 100%), radial-gradient(1200px 420px at 85% 0%, ${HERO.tint}33, transparent)`,
        }}
      />

      <div className="absolute inset-0 p-8 md:p-16 flex flex-col justify-center items-start text-left gap-4 z-10">
        <span className="text-cyan-300/90 text-sm font-medium">Sponsored</span>
        <h1 className="text-white text-4xl md:text-6xl font-semibold tracking-tight drop-shadow-xl">
          {HERO.title}
        </h1>
        <p className="text-zinc-200/90 max-w-3xl text-sm md:text-lg leading-relaxed">
          {HERO.synopsis}
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={onWatch}
            className="px-5 py-2.5 rounded-2xl bg-transparent text-white font-semibold hover:bg-white/5 transition border border-cyan-400/80"
          >
            {HERO.cta}
          </button>
          <button className="px-4 py-2.5 rounded-2xl bg-white/10 text-white/95 hover:bg-white/15 transition shadow-[inset_0_0_0_1px_rgba(255,255,255,.08)]">
            More Info
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ title, items, onPlay }) {
  return (
    <div className="mt-7 relative z-20">
      <div className="flex items-center justify-between pr-2 mb-2">
        <h2 className="text-white/95 text-xl md:text-2xl font-semibold">{title}</h2>
      </div>
      {/* allow vertical escape so lifted cards aren't clipped */}
      <div className="row-scroll flex gap-4 overflow-x-auto overflow-y-visible no-scrollbar pb-2 scroll-smooth snap-x snap-mandatory">
        {items.map((it) => (
          <Card key={it.id} item={it} onPlay={onPlay} />
        ))}
      </div>
    </div>
  );
}

// NEW: Hover-lift without cropping. The inner frame stays fixed; outer wrapper moves.
function Card({ item, onPlay }) {
  const playable = !!item.playable;

  return (
    // OUTER HITBOX (moves on hover)
    <div className="group relative snap-start" style={{ width: 360, height: 202, willChange: "transform" }}>
      {/* Hover lift (no scaling), glow outside the clipped frame */}
      <button
        onClick={() => playable && onPlay(item.id, item.videoUrl)}
        className="absolute inset-0 transition-transform duration-200 ease-[cubic-bezier(.2,.8,.2,1)] group-hover:-translate-y-2 focus-visible:-translate-y-2"
        aria-label={item.title}
      >
        {/* FIXED-SIZE FRAME (clipped, stable) */}
        <div className="relative w-full h-full rounded-[22px] overflow-hidden bg-black shadow-[0_10px_30px_rgba(0,0,0,.45)]">
          <img src={item.thumb} alt="" className="absolute inset-0 w-full h-full object-cover select-none pointer-events-none" draggable={false} />

          {/* bottom gradient for text */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent" />

          {/* title + pill */}
          <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
            <span className="text-white font-bold text-sm md:text-base drop-shadow-md">{item.title}</span>
            {!playable && (
              <span className="px-2 py-1 bg-black/70 text-white rounded-md text-[11px]">Releasing soon</span>
            )}
          </div>

          {/* soft cyan spotlight on hover (inside frame) */}
          <div className="pointer-events-none absolute inset-[-20%] opacity-0 group-hover:opacity-50 transition-opacity duration-200" style={{ background: "radial-gradient(600px 260px at 50% 100%, rgba(0,180,255,.28), transparent)" }} />
        </div>

        {/* glow outside the clipped corners */}
        <div className="pointer-events-none absolute -inset-1 rounded-[24px] opacity-0 group-hover:opacity-100 transition-opacity duration-200" style={{ boxShadow: "0 22px 70px rgba(0,160,255,.28)" }} />

        {/* progress bar if provided */}
        {typeof item.progress === 'number' && (
          <div className="absolute left-0 right-0 bottom-0 h-1 bg-white/15 rounded-b-[22px] overflow-hidden">
            <div className="h-full" style={{ width: `${Math.min(100, Math.max(0, item.progress * 100))}%`, background: 'linear-gradient(90deg,#00e5ff,#7b5cff)' }} />
          </div>
        )}
      </button>
    </div>
  );
}

export const PlayerOverlay = React.memo(forwardRef(({ url, onClose, seekTo = null, micListening, onMicDown, onMicUp, voiceQuery, currentVideoId, recapWords, currentWordIndex, setRecapWords, setCurrentWordIndex, setSeekTime }, ref) => {
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(0.9);
  const [played, setPlayed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [isFs, setIsFs] = useState(false);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);
  const playerRef = useRef(null);
  const containerRef = useRef(null);
  useImperativeHandle(ref, () => ({
    pauseVideo: () => {
      setPlaying(false);
    },
  }));

  useEffect(() => {
    if (!ready || !playerRef.current) return;
  
    // --- Priority 1: backend timestamp (seekTo)
    if (seekTo !== null) {
      console.log("⏩ Seeking to timestamp from backend:", seekTo);
      playerRef.current.seekTo(seekTo, "seconds");
      setPlaying(true);
  
      // clear seekTo safely after applying
      const timeout = setTimeout(() => {
        if (typeof setSeekTime === "function") {
          console.log("Cleared seekTo after backend seek");
          setSeekTime(null);
        }
      }, 1500);
  
      return () => clearTimeout(timeout);
    }
  
    // --- Priority 2: localStorage resume (only if no backend timestamp)
    // const key = `video-progress-${url}`;
    // const saved = localStorage.getItem(key);
    // if (saved) {
    //   const time = parseFloat(saved);
    //   if (!isNaN(time)) {
    //     console.log("📼 Seeking to saved localStorage position:", time);
    //     playerRef.current.seekTo(time, "seconds");
    //     setPlaying(true);
    //   }
    // }
  }, [ready, seekTo, url]);

  useEffect(() => {
    if (seekTo !== null && ready && playerRef.current) {
      console.log("⏩ Seeking to timestamp from backend:", seekTo);
      playerRef.current.seekTo(seekTo, "seconds");
      setPlaying(true);
  
      const timeout = setTimeout(() => {
        if (typeof setSeekTime === "function") {
          console.log("Cleared seekTo after applying backend seek");
          setSeekTime(null);
        }
      }, 1500); // safer delay
  
      return () => clearTimeout(timeout);
    }
  }, [seekTo, ready]);

  // useEffect(() => {
  //   if (!url || !playerRef.current) return;
  
  //   const key = `video-progress-${url}`;
  
  //   const interval = setInterval(() => {
  //     const currentTime = playerRef.current?.getCurrentTime?.();
  //     if (typeof currentTime === "number" && !isNaN(currentTime)) {
  //       localStorage.setItem(key, currentTime.toString());
  //     }
  //   }, 5000); // save every 5 seconds
  
  //   return () => clearInterval(interval);
  // }, [url]);

  useEffect(() => {
    setReady(false);
  }, [url]);
  
  useEffect(() => {
    let t; if (!url) return; const onMove = () => { setControlsVisible(true); clearTimeout(t); t = setTimeout(()=>setControlsVisible(false), 2200); };
    window.addEventListener('mousemove', onMove);
    t = setTimeout(()=>setControlsVisible(false), 2200);
    return () => { window.removeEventListener('mousemove', onMove); clearTimeout(t); };
  }, [url]);
  const fmt = (s) => { if (!Number.isFinite(s)) return '0:00'; const m = Math.floor(s/60), sec = Math.floor(s%60).toString().padStart(2,'0'); return `${m}:${sec}`; };
  const seek = (fraction) => {
    setPlayed(fraction);
    if (playerRef.current && typeof playerRef.current.seekTo === 'function') {
      playerRef.current.seekTo(fraction, 'fraction');
    }
  };
  const toggleFs = async () => { const el = containerRef.current; if (!document.fullscreenElement) { await el?.requestFullscreen?.(); setIsFs(true); } else { await document.exitFullscreen(); setIsFs(false); } };
  const handleClose = () => {
    setPlaying(false);              // stop playback immediately
    requestAnimationFrame(() => {   // wait a tick before removing from DOM
      setTimeout(onClose, 0);
    });
  };
  return (
    <AnimatePresence>
      {url && (
        <motion.div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.div ref={containerRef} className="relative w-[92vw] max-w-[1600px] aspect-video rounded-none overflow-hidden bg-black shadow-[0_50px_140px_rgba(0,0,0,.9)]" initial={{ opacity: 0.6 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.35, ease: EASE }}>
            <ReactPlayer 
              ref={(player) => { playerRef.current = player; }} 
              url={url} 
              playing={playing} 
              muted={muted} 
              volume={volume} 
              controls={false} 
              width="100%" 
              height="100%" 
              onProgress={(st)=> setPlayed(st.played)} 
              onDuration={(d)=> setDuration(d)}
              onReady={() => {
                console.log('ReactPlayer ready');
                setReady(true);
                setError(null);
              }}
              onError={(error) => {
                console.error('ReactPlayer error:', error);
                setError(`Failed to load video: ${error?.message || 'Unknown error'}`);
                setPlaying(false);
              }}
              onStart={() => {
                console.log('ReactPlayer started');
                setPlaying(true);
              }}
              config={{
                youtube: {
                  playerVars: {
                    autoplay: 0,
                    mute: muted ? 1 : 0,
                    modestbranding: 1,
                    rel: 0,
                  }
                }
              }}
            />

            {!ready && !error && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/80">
                <div className="text-center text-white p-6">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                  <p className="text-lg">Loading video...</p>
                </div>
              </div>
            )}

            {error && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/80">
                <div className="text-center text-white p-6">
                  <p className="text-lg mb-4">{error}</p>
                  <div className="space-y-2">
                    <button 
                      onClick={() => {
                        setError(null);
                        setReady(false);
                        setPlaying(false);
                      }} 
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg mr-2"
                    >
                      Try Again
                    </button>
                    <button 
                      onClick={handleClose} 
                      className="px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className={`absolute inset-0 flex flex-col ${controlsVisible ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300`}>
              <div className="flex justify-end p-3">
                <button onClick={handleClose} className="p-2 rounded-full bg-white/95 text-black hover:bg-white shadow" aria-label="Close"><X /></button>
              </div>
              <div className="mt-auto p-4">
                <div className="rounded-2xl bg-black/55 backdrop-blur-md px-4 py-3 shadow-[0_10px_40px_rgba(0,0,0,.6)]">
                  <div className="flex items-center gap-4">
                    <button onClick={()=>setPlaying(p=>!p)} className="w-10 h-10 rounded-full bg-white text-black flex items-center justify-center" aria-label="Play/Pause">{playing ? <Pause size={22}/> : <Play size={22}/>}</button>
                    
                    <button
                      onClick={() => {
                        const currentTime = played * duration;
                        fetch("http://localhost:8000/api/recap", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ video_id: currentVideoId, timestamp: Math.floor(currentTime) }),
                        })
                          .then((res) => res.json())
                          .then((data) => {
                            console.log("Recap response:", data);
                          //   if (data.audio_url) {
                          //     const audio = new Audio(data.audio_url);
                          //     audio.play();

                          //     if (data.summary) {
                          //       const words = data.summary.split(" ");
                          //       setRecapWords(words);
                          //       setCurrentWordIndex(0);
                              
                          //       const duration = 15000; // or any duration you want
                          //       const interval = duration / words.length;
                              
                          //       let idx = 0;
                          //       const timer = setInterval(() => {
                          //         idx += 1;
                          //         setCurrentWordIndex(idx);
                          //         if (idx >= words.length) {
                          //           clearInterval(timer);
                          //           setRecapWords([]);
                          //         }
                          //       }, interval);
                              
                          //       const audio = new Audio(data.audio_url);
                          //       audio.play();
                          //     }
                          //   }
                          // })
                          if (data.summary) {
                            const utterance = new SpeechSynthesisUtterance(data.summary);
                            window.speechSynthesis.speak(utterance);

                            const words = data.summary.split(" ");
                            setRecapWords(words);
                            setCurrentWordIndex(0);

                            const duration = 15000; // or any duration you want
                            const interval = duration / words.length;

                            let idx = 0;
                            const timer = setInterval(() => {
                              idx += 1;
                              setCurrentWordIndex(idx);
                              if (idx >= words.length) {
                                clearInterval(timer);
                                setRecapWords([]);
                              }
                            }, interval);

                            const audio = new Audio(data.audio_url);
                            audio.play();
                          }
                      }).catch((err) => console.error("Recap error:", err));
                    }} className="px-3 py-2 text-sm text-black bg-white hover:bg-gray-200 rounded-lg">Recap</button>

                    <div className="text-white/90 text-sm min-w-[54px]">{fmt(played*duration)}</div>
                    <div className="relative flex-1 h-2 rounded-full bg-white/25 cursor-pointer" onClick={(e)=>{ const r = e.currentTarget.getBoundingClientRect(); const f = Math.min(1, Math.max(0, (e.clientX - r.left)/r.width)); seek(f); }}>
                      <div className="absolute left-0 top-0 h-full rounded-full" style={{ width: `${played*100}%`, background: 'linear-gradient(90deg,#00e5ff,#7b5cff)' }} />
                    </div>
                    <div className="text-white/90 text-sm min-w-[54px] text-right">{fmt(duration)}</div>
                    <button
                      onMouseDown={onMicDown}
                      onMouseUp={onMicUp}
                      onTouchStart={onMicDown}
                      onTouchEnd={onMicUp}
                      className="relative w-10 h-10 rounded-full flex items-center justify-center bg-white/10 hover:bg-white/20"
                      aria-label="Voice Control">
                        <Mic className="text-white" size={16} />
                          {micListening && (
                            <motion.span
                              className="absolute inset-0 rounded-full"
                              initial={{ boxShadow: "0 0 0 0 rgba(0,229,255,.5)" }}
                              animate={{
                                boxShadow: [
                                  "0 0 0 0 rgba(0,229,255,.55)",
                                  "0 0 0 12px rgba(0,229,255,0)",
                                ],
                              }}
                              transition={{ duration: 1, repeat: Infinity, ease: "easeOut" }}
                            />
                          )}
                    </button>
                    <button onClick={()=>setMuted(m=>!m)} className="p-2 rounded-full bg-white/10 text-white hover:bg-white/20" aria-label="Mute">{muted || volume===0 ? <VolumeX/> : <Volume2/>}</button>
                    <input type="range" min={0} max={1} step={0.01} value={muted?0:volume} onChange={(e)=>{ const newVolume = parseFloat(e.target.value); setVolume(newVolume); setMuted(newVolume === 0); }} className="w-28 accent-cyan-400" />
                    <button onClick={toggleFs} className="p-2 rounded-full bg-white/10 text-white hover:bg-white/20" aria-label="Fullscreen">{isFs ? <Minimize/> : <Maximize/>}</button>
                  </div>
                </div>
              </div>
            </div>
            {micListening && voiceQuery && (
              <div className="absolute top-4 left-1/2 transform -translate-x-1/2 flex flex-col items-center z-50">

                {/* --- 🔁 Reuse mic style from sidebar --- */}
                <div className="relative w-10 h-10 rounded-full flex items-center justify-center">
                  <span className="absolute -inset-[7px] rounded-full blur-[8px] opacity-95 animate-spin-slow" style={{ background: "conic-gradient(from 0deg,#00e5ff,#7b5cff,#00e5ff)" }} />
                  <span className="absolute -inset-2 rounded-full blur-md opacity-50" style={{ background: "radial-gradient(circle, rgba(0,229,255,.45), rgba(123,92,255,.35) 60%, transparent 70%)" }} />
                  <span className="absolute inset-0 rounded-full bg-[#1b1f26] shadow-[inset_0_0_0_2px_rgba(255,255,255,.08)]" />
                  <Mic className="relative text-white" size={16} />
                </div>

                {/* 🎤 Transcribed voice text under mic */}
                <div className="mt-2 text-xl font-semibold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 drop-shadow-[0_0_8px_white] text-center px-4">
                  {voiceQuery}
                </div>
              </div>
            )}
            {recapWords.length > 0 && (
              <div className="absolute top-20 left-1/2 transform -translate-x-1/2 z-50">
                <div className="mt-2 text-xl font-semibold text-center px-4 flex flex-wrap justify-center">
                  {recapWords.map((word, i) => (
                    <span
                      key={i}
                      className={
                        i === currentWordIndex
                          ? "text-white font-bold mx-1 drop-shadow-[0_0_8px_white]"
                          : "text-gray-400 mx-1"
                      }
                    >
                      {word}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
})
);

export default function STREAMING_OS_REPLICA() {
  const [playerUrl, setPlayerUrl] = useState(null);
  const [currentVideoId, setCurrentVideoId] = useState(null);
  const playerRef = useRef(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [seekTime, setSeekTime] = useState(null);
  const {listening, start, stop } = useSpeech(currentVideoId, setSearchQuery, () => playerRef.current?.pauseVideo?.(), setPlayerUrl, setCurrentVideoId, setSeekTime);
  const [recapWords, setRecapWords] = useState([]);
  const [currentWordIndex, setCurrentWordIndex] = useState(0);

  const handleBackendNavigation = (video_id, timestamp) => {
    const url = VIDEO_ID_MAP[video_id];
    if (url) {
      setPlayerUrl(url);
      setSeekTime(timestamp);
    } else {
      console.warn("Video ID not found:", video_id);
    }
  };

  const bg = useMemo(() => ({
    background:
      `radial-gradient(1200px 600px at 20% -10%, ${HERO.tint}20, transparent), radial-gradient(900px 600px at 100% 0%, rgba(130,80,255,.10), transparent), linear-gradient(180deg, #0b0e13 0%, #0b0e13 40%, #0b0e13 100%)`,
  }), []);

  return (
    <div className="min-h-screen w-full text-white" style={bg}>
      <LeftNavBar micListening={listening} onMicDown={start} onMicUp={stop} />
      <div className="ml-[96px] w-[calc(100vw-96px)] overflow-x-hidden">
        <TopBanner />
        <div className="px-6 mt-4">
          <input
            type="text"
            placeholder="Search by voice or title..."
            className="w-full px-4 py-2 rounded-lg bg-white/10 text-white placeholder:text-white/50 focus:outline-none focus:ring-2 focus:ring-cyan-400"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <Hero onWatch={() => setPlayerUrl(HERO.videoUrl)} />
        {ROWS.map((row) => (
          <Row key={row.id} title={row.title} items={row.items} onPlay={(videoId, videoUrl) => 
            {setCurrentVideoId(videoId);
              setPlayerUrl(videoUrl);
          }} />
        ))}
      </div>
      <PlayerOverlay 
        url={playerUrl} 
        onClose={() => setPlayerUrl("")} 
        seekTo={seekTime}
        micListening={listening}
        onMicDown={start}
        onMicUp={stop}
        ref={playerRef}
        voiceQuery={searchQuery}
        currentVideoId={currentVideoId}
        recapWords={recapWords}
        currentWordIndex={currentWordIndex}
        setRecapWords={setRecapWords}
        setCurrentWordIndex={setCurrentWordIndex}
        setSeekTime={setSeekTime}
      />
      
      <style>{`
        .no-scrollbar { scrollbar-width: none; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .animate-spin-slow { animation: spin 6s linear infinite; }
        .row-scroll { -webkit-mask-image: linear-gradient(black, black); }
      `}</style>
    </div>
  );
}
