import { useState, useEffect } from 'react';
import { Share2, RefreshCw, Clock } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import AutocompleteInput from '@/components/ui/AutocompleteInput';

const GuessGame = () => {
  const [gameState, setGameState] = useState({
    currentImage: '',
    hintText: null,
    hintLevel: 0,
    guesses: [],
    gameOver: false,
    gameId: null,
    message: '',
    loading: true,
    nextReset: null,
    currentDate: null,
    playerName: null
  });
  
  const [guess, setGuess] = useState('');
  const [timeUntilReset, setTimeUntilReset] = useState('');
  const [players, setPlayers] = useState([]);
  const [filteredPlayers, setFilteredPlayers] = useState([]);

  const formatTimeUntilReset = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };
  
  const checkStoredGame = () => {
    const stored = localStorage.getItem('footballGuessGame');
    if (stored) {
      const { date, guesses, hintLevel, gameOver, playerName } = JSON.parse(stored);
      if (date === gameState.currentDate) {
        setGameState(prev => ({
          ...prev,
          guesses,
          hintLevel,
          gameOver,
          playerName
        }));
        return true;
      }
    }
    return false;
  };

const saveGameState = () => {
  const toStore = {
    date: gameState.currentDate,
    guesses: gameState.guesses,
    hintLevel: gameState.hintLevel,
    gameOver: gameState.gameOver,
    playerName: gameState.playerName
  };
  localStorage.setItem('footballGuessGame', JSON.stringify(toStore));
};
  
  const fetchGameState = async () => {
    setGameState(prev => ({ ...prev, loading: true }));
    try {
      const response = await fetch('http://localhost:5000/api/game-state');
      const data = await response.json();
      
      setGameState(prev => ({
        ...prev,
        currentImage: data.blurred_image,
        gameId: data.game_id,
        nextReset: data.next_reset,
        currentDate: data.current_date,
        loading: false
      }));
      
      checkStoredGame();
      
    } catch (error) {
      setGameState(prev => ({
        ...prev,
        message: 'Error loading game',
        loading: false
      }));
    }
  };

  const getImageSource = (imageData) => {
    if (!imageData) return '';
    // If it's a full URL
    if (imageData.startsWith('http')) {
      return imageData;
    }
    // If it's already a data URL
    if (imageData.startsWith('data:image')) {
      return imageData;
    }
    // If it's a base64 string
    return `data:image/jpeg;base64,${imageData}`;
  };

  
  const fetchPlayerNames = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/player-names');
      const playerNames = await response.json();
      setPlayers(playerNames);
      setFilteredPlayers(playerNames);
    } catch (error) {
      console.error('Error fetching player names:', error);
    }
  };

  const handleGuess = async (e) => {
    e.preventDefault();
    
    if (!guess.trim()) return;
    
    try {
      const response = await fetch('http://localhost:5000/api/guess', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          guess: guess.trim(),
          hint_level: gameState.hintLevel
        })
      });
      
      const data = await response.json();
      
      const newGuesses = [...gameState.guesses, {
        guess: guess,
        correct: data.correct,
        hintLevel: gameState.hintLevel
      }];
      
      if (data.correct) {
        setGameState(prev => ({
          ...prev,
          guesses: newGuesses,
          gameOver: true,
          currentImage: data.image_url,  // Use original image
          playerName: data.player_name,
          message: 'Congratulations! You got it right!'
        }));
      } else {
        if (gameState.hintLevel >= 4) {
          setGameState(prev => ({
            ...prev,
            guesses: newGuesses,
            gameOver: true,
            currentImage: data.image_url,  // Use original image
            playerName: data.player_name,
            message: 'Game Over! Try again tomorrow!'
          }));
        } else {
          // Regular hint progression
          const newImage = data.image_url || data.hint_image;
          
          setGameState(prev => ({
            ...prev,
            guesses: newGuesses,
            hintLevel: prev.hintLevel + 1,
            currentImage: newImage,
            hintText: data.hint_text,
            message: 'Wrong guess! Here\'s your next hint:'
          }));
        }
      }
      
      setGuess('');
    } catch (error) {
      console.error('Error submitting guess:', error);
      setGameState(prev => ({
        ...prev,
        message: 'Error submitting guess'
      }));
    }
  };

  const shareResult = () => {
    const scoreDisplay = gameState.guesses.map(g => 
      g.correct ? '🟩' : '🟥'
    ).join('');
    
    const text = `Football Player Guessing Game ${gameState.currentDate}\n${scoreDisplay}\nNext player in ${timeUntilReset}!`;
    
    if (navigator.share) {
      navigator.share({
        text,
        title: 'Football Player Guessing Game'
      }).catch(() => {
        navigator.clipboard.writeText(text);
        setGameState(prev => ({
          ...prev,
          message: 'Result copied to clipboard!'
        }));
      });
    } else {
      navigator.clipboard.writeText(text);
      setGameState(prev => ({
        ...prev,
        message: 'Result copied to clipboard!'
      }));
    }
  };

  useEffect(() => {
    fetchGameState();
    
    const timer = setInterval(() => {
      if (gameState.nextReset) {
        const newTime = gameState.nextReset - 1;
        setGameState(prev => ({
          ...prev,
          nextReset: newTime
        }));
        setTimeUntilReset(formatTimeUntilReset(newTime));
      }
    }, 1000);
    
    const checkReset = setInterval(() => {
      const now = new Date();
      if (now.getHours() === 0 && now.getMinutes() === 0) {
        fetchGameState();
      }
    }, 60000);
    
    return () => {
      clearInterval(timer);
      clearInterval(checkReset);
    };
  }, []);
  
  useEffect(() => {
    if (gameState.nextReset) {
      setTimeUntilReset(formatTimeUntilReset(gameState.nextReset));
    }
  }, [gameState.nextReset]);
  
  useEffect(() => {
    if (gameState.currentDate) {
      saveGameState();
    }
  }, [gameState.guesses, gameState.hintLevel, gameState.gameOver]);

  useEffect(() => {
    fetchPlayerNames();
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <Card className="max-w-2xl mx-auto">
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle className="text-2xl font-bold">
              Guess the Football Player
            </CardTitle>
            <div className="flex items-center text-sm text-gray-500">
              <Clock className="w-4 h-4 mr-1" />
              <span>Next player in: {timeUntilReset}</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {gameState.loading ? (
            <div className="flex justify-center p-8">
              <RefreshCw className="animate-spin" />
            </div>
          ) : (
            <>
            <div className="aspect-square relative mb-6">
            <img
                src={getImageSource(gameState.currentImage)}
                alt="Football player"
                className="w-full h-full object-cover rounded-lg"
            />
            </div>
            
            {gameState.gameOver && gameState.playerName && (
                <Alert className="mb-4">
                <AlertDescription>
                    The player was: <span className="font-bold">{gameState.playerName}</span>
                </AlertDescription>
                </Alert>
            )}

            {gameState.message && (
                <Alert className={`mb-4 ${gameState.gameOver ? 'bg-secondary' : ''}`}>
                <AlertDescription>{gameState.message}</AlertDescription>
                <AlertDescription>{gameState.hintText}</AlertDescription>
                </Alert>
            )}
                        
                <form onSubmit={handleGuess} className="space-y-4">
                  <AutocompleteInput
                    value={guess}
                    onChange={setGuess}
                    options={players}
                    placeholder="Enter player's name"
                    disabled={gameState.gameOver}
                    className="w-full"
                  />                   
                <div className="flex gap-2">
                  <Button 
                    type="submit" 
                    disabled={gameState.gameOver}
                    className="flex-1"
                  >
                    Guess
                  </Button>
                  
                  {gameState.gameOver && (
                    <Button
                      onClick={shareResult}
                      variant="outline"
                      className="flex items-center"
                    >
                      <Share2 className="w-4 h-4 mr-2" />
                      Share
                    </Button>
                  )}
                </div>
              </form>
              
              <div className="mt-6 flex flex-wrap gap-2">
                {gameState.guesses.map((g, i) => (
                  <div
                    key={i}
                    className={`w-8 h-8 rounded ${
                      g.correct ? 'bg-green-500' : 'bg-red-500'
                    }`}
                  />
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default GuessGame;