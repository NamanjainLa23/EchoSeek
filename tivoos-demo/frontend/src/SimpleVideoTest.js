import React from 'react';
import ReactPlayer from 'react-player';

function SimpleVideoTest() {
  return (
    <div style={{ padding: '20px', backgroundColor: '#000', color: '#fff', minHeight: '100vh' }}>
      <h1>Simple ReactPlayer Test</h1>
      
      <div style={{ marginBottom: '20px' }}>
        <h3>Test 1: Rick Roll (should work)</h3>
        <ReactPlayer
          url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
          controls={true}
          width="100%"
          height="300px"
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Test 2: Your URL</h3>
        <ReactPlayer
          url="https://www.youtube.com/watch?v=aqz-KE-bpKQ"
          controls={true}
          width="100%"
          height="300px"
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Test 3: Another YouTube URL</h3>
        <ReactPlayer
          url="https://www.youtube.com/watch?v=ysz5S6PUM-U"
          controls={true}
          width="100%"
          height="300px"
        />
      </div>

      <div style={{ padding: '10px', backgroundColor: '#333', borderRadius: '4px' }}>
        <h4>Instructions:</h4>
        <p>1. Check browser console (F12) for any errors</p>
        <p>2. Try clicking play on each video</p>
        <p>3. See which ones load and work</p>
      </div>
    </div>
  );
}

export default SimpleVideoTest;
