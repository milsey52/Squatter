import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react';
import DiceBox from '@3d-dice/dice-box';

const DiceRoller = forwardRef(({ onRollComplete }, ref) => {
  const diceBoxRef = useRef(null);
  const containerRef = useRef(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [isRolling, setIsRolling] = useState(false);

  useEffect(() => {
    if (isInitialized || !containerRef.current) return;

    // Initialize dice box with canvas in the container
    const diceBox = new DiceBox(
      '#dice-canvas',
      {
        assetPath: 'https://unpkg.com/@3d-dice/dice-box@1.1.1/dist/assets/',
        theme: 'default',
        scale: 5,
        gravity: 1.5,
        mass: 1,
        friction: 0.8,
        restitution: 0.3,
        linearDamping: 0.5,
        angularDamping: 0.4,
        spinForce: 5,
        throwForce: 4,
        startingHeight: 8,
        settleTimeout: 2500,
        offscreen: false,
        delay: 10,
      }
    );

    diceBox.init().then(() => {
      diceBoxRef.current = diceBox;
      setIsInitialized(true);
      console.log('DiceBox initialized successfully');
    }).catch(err => {
      console.error('Failed to initialize DiceBox:', err);
    });

    // Cleanup on unmount
    return () => {
      if (diceBoxRef.current) {
        diceBoxRef.current.clear();
      }
    };
  }, []);

  // Method to roll dice with specific values
  const roll = async (die1, die2) => {
    if (!diceBoxRef.current || !isInitialized) {
      console.warn('DiceBox not initialized yet');
      if (onRollComplete) {
        onRollComplete(die1, die2);
      }
      return;
    }

    setIsRolling(true);

    try {
      // Clear any previous dice
      diceBoxRef.current.clear();

      // Roll two dice with specific values
      await diceBoxRef.current.roll([
        { qty: 1, sides: 6, value: die1 },
        { qty: 1, sides: 6, value: die2 }
      ]);

      // Wait for dice to settle before notifying completion
      setTimeout(() => {
        setIsRolling(false);
        if (onRollComplete) {
          onRollComplete(die1, die2);
        }
        // Clear dice after a brief display
        setTimeout(() => {
          if (diceBoxRef.current) {
            diceBoxRef.current.clear();
          }
        }, 1500);
      }, 2500);
    } catch (error) {
      console.error('Error rolling dice:', error);
      setIsRolling(false);
      // Fallback if animation fails
      if (onRollComplete) {
        onRollComplete(die1, die2);
      }
    }
  };

  // Expose roll method to parent via ref
  useImperativeHandle(ref, () => ({
    roll,
    isInitialized,
    isRolling
  }));

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: isRolling ? 1000 : -1,
        opacity: isRolling ? 1 : 0,
        transition: 'opacity 0.3s ease'
      }}
    >
      <canvas
        id="dice-canvas"
        style={{
          width: '100%',
          height: '100%'
        }}
      />
    </div>
  );
});

DiceRoller.displayName = 'DiceRoller';

export default DiceRoller;
