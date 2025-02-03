import React, { useState, useRef } from 'react';

function ImageComponent() {
  const [loading, setLoading] = useState(true);
  const [imageError, setImageError] = useState(false);
  const imgRef = useRef(null);

  return (
    <div
      style={{
        width: '640px',
        height: '480px',
        borderRadius: '12px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
        marginBottom: '1.5rem',
        backgroundColor: '#f0f0f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}
    >
      {loading && !imageError && (
        <div
          style={{
            width: '40px',
            height: '40px',
            border: '4px solid #f0f0f0',
            borderTop: '4px solid #007AFF',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }}
        />
      )}
      <img
        ref={imgRef}
        alt="RTMP Stream"
        style={{
          width: '100%',
          height: '100%',
          borderRadius: '12px',
          display: loading || imageError ? 'none' : 'block',
        }}
        onLoad={() => setLoading(false)}
        onError={() => {
          setLoading(false);
          setImageError(true);
        }}
      />
      {imageError && (
        <p
          style={{
            position: 'absolute',
            color: '#888',
            fontSize: '1.2rem',
            textAlign: 'center',
          }}
        >
          이미지가 로드되지 않았습니다.
        </p>
      )}
    </div>
  );
}

export default ImageComponent;
