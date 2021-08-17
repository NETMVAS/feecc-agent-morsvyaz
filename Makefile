test:
		cd feecc_hub_src/ && PYTHONPATH=. pytest .. && cd ..

cleanup:
		rm -rfv feecc_hub_src/output/* feecc_hub_src/hub.log
