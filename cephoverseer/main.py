import sys
import qasync
from PyQt5.QtWidgets import QApplication
from cephoverseer.ui.main_window import MainWindow
from cephoverseer.workers.polling_worker import PollingWorker
from cephoverseer.models.config import ConfigManager

async def main_async(app: QApplication):
    """
    The asynchronous main function.
    Initializes the UI and background workers, then integrates them.
    """
    # Load configuration
    config_manager = ConfigManager()

    main_window = MainWindow()
    main_window.show()

    # Initialize the Polling Worker
    # Note: We run start_polling() as an asyncio task, keeping it non-blocking
    worker = PollingWorker(config_manager=config_manager, interval_seconds=1.5)

    
    # Connect signals from worker to UI slots
    worker.data_fetched.connect(main_window.update_ui_with_data)
    
    # Fire up the background polling loop
    import asyncio
    polling_task = asyncio.create_task(worker.start_polling())

    # Keep the async loop running as long as the UI is alive
    try:
        # Await a future that never resolves to keep the event loop alive until window closes
        # The QEventLoop (via qasync) handles the window close events internally and will shut down.
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        worker.stop()
        polling_task.cancel()

def main():
    """
    Entry point for the application.
    Sets up the QApplication and the qasync EventLoop.
    """
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Clean, cross-platform look

    # Set up the asyncio event loop to integrate with PyQt5
    loop = qasync.QEventLoop(app)
    import asyncio
    asyncio.set_event_loop(loop)

    with loop:
        # Run the async main function
        loop.run_until_complete(main_async(app))

if __name__ == "__main__":
    main()
