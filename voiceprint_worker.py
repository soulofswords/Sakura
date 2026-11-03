"""Isolated optional CPU speaker encoder. No microphone or account access."""
import argparse,json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',required=True);parser.add_argument('--audio');args=parser.parse_args()
    from speechbrain.inference.classifiers import EncoderClassifier
    from speechbrain.utils.fetching import LocalStrategy
    folder=Path(args.model)
    if not args.audio:
        from huggingface_hub import snapshot_download
        snapshot_download('speechbrain/spkrec-ecapa-voxceleb',revision='0f99f2d0ebe89ac095bcc5903c4dd8f72b367286',local_dir=folder,
                          allow_patterns=['hyperparams.yaml','embedding_model.ckpt','mean_var_norm_emb.ckpt','classifier.ckpt','label_encoder.txt'])
    encoder=EncoderClassifier.from_hparams(source=str(folder),overrides={'pretrained_path':str(folder)},
        savedir=str(folder),
        run_opts={'device':'cpu'},local_strategy=LocalStrategy.COPY)
    if args.audio:
        import soundfile as sf
        import torch
        signal,rate=sf.read(args.audio,dtype='float32',always_2d=False)
        if signal.ndim>1:signal=signal.mean(axis=1)
        if not .35<=len(signal)/rate<=30:raise ValueError('Use a clear recording between 0.35 and 30 seconds.')
        if rate!=16000:
            from scipy.signal import resample_poly
            from math import gcd
            divisor=gcd(rate,16000);signal=resample_poly(signal,16000//divisor,rate//divisor)
        if float((signal**2).mean())<.000004:raise ValueError('Recording is too quiet.')
        vector=encoder.encode_batch(torch.from_numpy(signal).unsqueeze(0)).detach().cpu().reshape(-1).tolist()
        print('SAKURA_VECTOR:'+json.dumps(vector),flush=True)
    else:print('SAKURA_READY',flush=True)


if __name__=='__main__':main()
