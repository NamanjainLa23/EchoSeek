import React from 'react';
import ReactPlayer from 'react-player';

function BasicTest() {
  return (
    <div style={{ padding: '20px', backgroundColor: '#000', color: '#fff', minHeight: '100vh' }}>
      <h1>Basic ReactPlayer Test</h1>
      
      <div style={{ marginBottom: '20px' }}>
        <h3>Test with minimal props:</h3>
        <ReactPlayer
          url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
          controls
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Test with width/height:</h3>
        <ReactPlayer
          url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
          controls
          width="100%"
          height="300px"
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Test with your URL:</h3>
        <ReactPlayer
          url="https://www.youtube.com/watch?v=aqz-KE-bpKQ"
          controls
          width="100%"
          height="300px"
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Test with direct iframe (fallback):</h3>
        <iframe
          width="100%"
          height="300"
          src="https://www.youtube.com/embed/dQw4w9WgXcQ"
          title="YouTube video player"
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        ></iframe>
      </div>

      <div style={{ padding: '10px', backgroundColor: '#333', borderRadius: '4px' }}>
        <h4>Debug Info:</h4>
        <p>ReactPlayer version: 3.3.3</p>
        <p>Check console for any errors</p>
        <p>If ReactPlayer doesn't work, the iframe should work as a fallback</p>
      </div>
    </div>
  );
}

export default BasicTest;
