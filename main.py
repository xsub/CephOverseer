import sys
import qasync
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from workers.polling_worker import PollingWorker
from models.config import ConfigManager

async def main_async(app: QApplication):
    """
    The asynchronous main function.
    Initializes the UI and background workers, then integrates them.
    """
    import asyncio
    # Load configuration
    config_manager = ConfigManager()

    main_window = MainWindow(config_manager=config_manager)
    main_window.show()

    # Initialize the Polling Worker
    # Note: We run start_polling() as an asyncio task, keeping it non-blocking
    worker = PollingWorker(config_manager=config_manager, interval_seconds=1.5)
    
    # Connect signals from worker to UI slots
    worker.data_fetched.connect(main_window.update_ui_with_data)
    worker.log_event.connect(main_window.log_event)
    
    # Initial startup log
    mode_text = "Simulation Mode (Mock Data)" if worker.use_mock else "Real Network Mode"
    main_window.log_event(f"CephOverseer started in {mode_text}.")
    polling_task = asyncio.create_task(worker.start_polling())

    def on_settings_changed():
        nonlocal polling_task
        print("Settings changed, restarting polling worker...")
        worker.stop()
        polling_task.cancel()
        
        # Refresh configuration
        config_manager.load_config()
        
        # Propagate the simulation flag to the worker
        worker.use_mock = config_manager.use_simulation
        
        mode_text = "Simulation Mode (Mock Data)" if worker.use_mock else "Real Network Mode"
        main_window.log_event(f"Worker restarting in {mode_text}.")
        
        if not worker.use_mock:
            worker._init_real_clients()
        else:
            worker.clients.clear()
            
        polling_task = asyncio.create_task(worker.start_polling())

    def perform_pool_action(cluster_name: str, pool_name: str, prop: str, value: int):
        main_window.log_event(f"Executing set {prop}={value} on pool '{pool_name}' in {cluster_name}...")
        
        async def do_action():
            if worker.use_mock:
                import asyncio
                await asyncio.sleep(0.5)
                main_window.log_event(f"[Mock] Successfully set {prop}={value} on pool '{pool_name}'")
                return

            client_tuple = worker.clients.get(cluster_name)
            if client_tuple and client_tuple[1]:
                mgr_client = client_tuple[1]
                try:
                    success = await mgr_client.update_pool(pool_name, {prop: value})
                    if success:
                        main_window.log_event(f"Successfully updated pool '{pool_name}'")
                    else:
                        main_window.log_event(f"Failed to update pool '{pool_name}'")
                except Exception as e:
                    main_window.log_event(f"Error updating pool '{pool_name}': {e}")
            else:
                main_window.log_event(f"Error: MGR Client not found for {cluster_name}")

        import asyncio
        asyncio.create_task(do_action())

    main_window.pool_action_requested.connect(perform_pool_action)

    def perform_osd_action(cluster_name: str, osd_id: int, action: str):
        main_window.log_event(f"Executing '{action}' on osd.{osd_id} in {cluster_name}...")
        
        # Fire-and-forget task
        async def do_action():
            if worker.use_mock:
                await asyncio.sleep(0.5)
                main_window.log_event(f"[Mock] Successfully marked osd.{osd_id} '{action}'")
                return

            client_tuple = worker.clients.get(cluster_name)
            if client_tuple and client_tuple[1]:
                mgr_client = client_tuple[1]
                try:
                    success = await mgr_client.set_osd_status(osd_id, action)
                    if success:
                        main_window.log_event(f"Successfully marked osd.{osd_id} '{action}'")
                    else:
                        main_window.log_event(f"Failed to mark osd.{osd_id} '{action}'")
                except Exception as e:
                    main_window.log_event(f"Error performing action on osd.{osd_id}: {e}")
            else:
                main_window.log_event(f"Error: MGR Client not found for {cluster_name}")

        asyncio.create_task(do_action())

    main_window.settings_changed.connect(on_settings_changed)
    main_window.osd_action_requested.connect(perform_osd_action)

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
