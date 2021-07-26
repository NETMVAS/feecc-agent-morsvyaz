test:
		cd feecc_hub_src/ && PYTHONPATH=. pytest .. && cd ..

cleanup:
		rm -rf feecc_hub_src/output
