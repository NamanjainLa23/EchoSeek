import React, { useState } from 'react';
import ReactPlayer from 'react-player';

function VideoTest() {
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(true);
  const [volume, setVolume] = useState(0.8);
  const [played, setPlayed] = useState(0);
  const [duration, setDuration] = useState(0);

  const testUrls = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ", // Rick Roll - known to work
    "https://www.youtube.com/watch?v=aqz-KE-bpKQ", // Your original URL
    "https://youtu.be/aqz-KE-bpKQ", // Short format
    "https://www.youtube.com/watch?v=ysz5S6PUM-U", // Another test
  ];

  const [currentUrl, setCurrentUrl] = useState(testUrls[0]);

  const handleProgress = (state) => {
    setPlayed(state.played);
    console.log('Progress:', state);
  };


  const handleReady = () => {
    console.log('Video is ready to play');
    // Try to get duration from the player
    setTimeout(() => {
      const player = document.querySelector('iframe');
      if (player) {
        console.log('YouTube iframe found');
      }
    }, 1000);
  };

  const handleError = (error) => {
    console.error('Video error:', error);
  };

  const handleStart = () => {
    console.log('Video started playing');
  };

  return (
    <div style={{ padding: '20px', backgroundColor: '#000', color: '#fff', minHeight: '100vh' }}>
      <h1>ReactPlayer YouTube Test</h1>
      
      <div style={{ marginBottom: '20px' }}>
        <h3>Test URLs:</h3>
        {testUrls.map((url, index) => (
          <button
            key={index}
            onClick={() => setCurrentUrl(url)}
            style={{
              margin: '5px',
              padding: '10px',
              backgroundColor: currentUrl === url ? '#007bff' : '#333',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Test {index + 1}
          </button>
        ))}
      </div>

      <div style={{ marginBottom: '20px' }}>
        <p><strong>Current URL:</strong> {currentUrl}</p>
      </div>

      <div style={{ 
        position: 'relative', 
        width: '100%', 
        maxWidth: '800px', 
        marginBottom: '20px',
        backgroundColor: '#222'
      }}>
        <ReactPlayer
          url={currentUrl}
          playing={playing}
          muted={muted}
          volume={volume}
          controls={true}
          width="100%"
          height="400px"
          onProgress={handleProgress}
          onReady={handleReady}
          onError={handleError}
          onStart={handleStart}
          config={{
            youtube: {
              playerVars: {
                autoplay: 0,
                mute: muted ? 1 : 0,
                modestbranding: 1,
                rel: 0,
                showinfo: 0,
              }
            }
          }}
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <button
          onClick={() => setPlaying(!playing)}
          style={{
            padding: '10px 20px',
            margin: '5px',
            backgroundColor: playing ? '#dc3545' : '#28a745',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {playing ? 'Pause' : 'Play'}
        </button>

        <button
          onClick={() => setMuted(!muted)}
          style={{
            padding: '10px 20px',
            margin: '5px',
            backgroundColor: muted ? '#ffc107' : '#17a2b8',
            color: '#000',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {muted ? 'Unmute' : 'Mute'}
        </button>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label>
          Volume: 
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={muted ? 0 : volume}
            onChange={(e) => {
              const newVolume = parseFloat(e.target.value);
              setVolume(newVolume);
              setMuted(newVolume === 0);
            }}
            style={{ marginLeft: '10px' }}
          />
          {Math.round((muted ? 0 : volume) * 100)}%
        </label>
      </div>

      <div>
        <p>Progress: {Math.round(played * 100)}%</p>
        <p>Duration: {Math.round(duration)} seconds</p>
        <p>Time: {Math.round(played * duration)} / {Math.round(duration)} seconds</p>
      </div>

      <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#333', borderRadius: '4px' }}>
        <h4>Console Logs:</h4>
        <p>Check your browser console (F12) for detailed logs</p>
      </div>
    </div>
  );
}

export default VideoTest;
